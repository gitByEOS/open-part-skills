#!/usr/bin/env node

import { access, mkdir, readdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import readline from "node:readline";
import process from "node:process";

const DEFAULT_TIMEOUT_MS = 45_000;
const DEFAULT_RETRIES = 3;
const MAX_RETRIES = 3;
const BOOLEAN_OPTIONS = new Set(["--visible", "--stealth"]);
const OPTION_NAMES_WITH_VALUES = new Set([
  "--out",
  "--output-dir",
  "--wait",
  "--timeout",
  "--wait-until",
  "--retries",
  "--selector",
  "--format",
  "--state",
  "--save-state",
]);
const DEFAULT_HUMAN_TIMEOUT_MS = 300_000;
const HUMAN_POST_WAIT_MS = 2_000;
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SKILL_ROOT = resolve(process.env.WFP_PATH ?? dirname(SCRIPT_PATH), process.env.WFP_PATH ? "." : "..");
const RUNTIME_ROOT = join(SKILL_ROOT, "runtime");
const DEPENDENCY_ROOT = join(RUNTIME_ROOT, "node");
const DEFAULT_TASKS_DIR = "/tmp/wfp-tasks";
const DEFAULT_EVIDENCE_DIR = "/tmp/wfp-evidence";
const DEFAULT_STATE_DIR = "/tmp/wfp-states";
const RUN_HASH_LENGTH = 8;
const URL_LABEL_MAX_LENGTH = 40;
const RUN_NAME_VERSION = "url-v1";

function printUsage() {
  console.error(`Usage:
  WFP_PATH=/path/to/skills/webfetch-plus
  cd "$WFP_PATH" && bash bin/wfp.sh <url> [options]

Options:
  --out <path>             Write output to this exact path
  --output-dir <path>      Write a unique flat output file into this directory
  --visible                Show browser window; default is hidden/headless
  --stealth                Use CloakBrowser's patched Chromium for stronger anti-WAF bypass
  --wait <ms>              Wait after navigation before extraction
  --timeout <ms>           Navigation timeout, default ${DEFAULT_TIMEOUT_MS}
  --wait-until <state>     load, domcontentloaded, networkidle; default networkidle
  --retries <1-3>          Max attempts, default ${DEFAULT_RETRIES}
  --selector <css>         Extract only a specific CSS selector
  --format <markdown|text|html>
  --state <path>           Load Playwright storageState JSON (cookies/localStorage)
  --save-state <path>      Save storageState after a successful fetch

When --state is omitted, reuse the newest valid matching state from ${DEFAULT_STATE_DIR}.
`); // logs go to stderr; stdout is reserved for output path

}

function parseTokens(args) {
  const options = new Map();
  const positional = [];

  for (let index = 0; index < args.length; index += 1) {
    const token = args[index];

    if (!token.startsWith("--")) {
      positional.push(token);
      continue;
    }

    if (BOOLEAN_OPTIONS.has(token)) {
      options.set(token, true);
      continue;
    }

    if (!OPTION_NAMES_WITH_VALUES.has(token)) {
      throw new Error(`Unknown option: ${token}`);
    }

    const value = args[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`${token} requires a value`);
    }

    options.set(token, value);
    index += 1;
  }

  return { options, positional };
}

function readOption(args, name, fallback = undefined) {
  return args.get(name) ?? fallback;
}

function readNumberOption(args, name, fallback) {
  const rawValue = readOption(args, name, String(fallback));
  const value = Number(rawValue);

  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${name} must be a non-negative number`);
  }
  return value;
}

function readIntegerOption(args, name, fallback, max) {
  const value = readNumberOption(args, name, fallback);

  if (!Number.isInteger(value) || value < 1 || value > max) {
    throw new Error(`${name} must be an integer between 1 and ${max}`);
  }
  return value;
}

function parseArgs(argv) {
  const args = getCliArgs(argv);
  const isHelp = args.includes("--help") || args.includes("-h");
  const { options, positional } = parseTokens(
    args.filter((arg) => arg !== "--help" && arg !== "-h"),
  );
  const [url, ...extraArgs] = positional;

  if (isHelp || !url) {
    printUsage();
    process.exit(isHelp ? 0 : 1);
  }

  if (extraArgs.length > 0) {
    throw new Error(`Unexpected positional arguments: ${extraArgs.join(", ")}`);
  }

  return {
    url,
    outPath: readOption(options, "--out"),
    outputDir: readOption(options, "--output-dir"),
    visible: options.has("--visible"),
    stealth: options.has("--stealth"),
    waitMs: readNumberOption(options, "--wait", 0),
    timeoutMs: readNumberOption(options, "--timeout", DEFAULT_TIMEOUT_MS),
    waitUntil: readOption(options, "--wait-until", "networkidle"),
    retries: readIntegerOption(options, "--retries", DEFAULT_RETRIES, MAX_RETRIES),
    selector: readOption(options, "--selector"),
    format: readOption(options, "--format", "markdown"),
    humanChallenge: process.env.WFP_HUMAN_CHALLENGE === "1",
    humanTimeoutMs: readHumanTimeout(),
    statePath: readOption(options, "--state"),
    saveStatePath: readOption(options, "--save-state"),
  };
}

function readHumanTimeout() {
  const rawValue = process.env.WFP_HUMAN_TIMEOUT_MS;
  if (rawValue === undefined) return DEFAULT_HUMAN_TIMEOUT_MS;
  const value = Number(rawValue);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error("WFP_HUMAN_TIMEOUT_MS must be a non-negative number");
  }
  return value;
}

function getCliArgs(argv) {
  const firstArg = argv[1] ?? "";
  const isEvalImport = firstArg.startsWith("http://") || firstArg.startsWith("https://") || firstArg.startsWith("-");

  return argv.slice(isEvalImport ? 1 : 2);
}

function normalizeUrl(url) {
  let parsedUrl;
  try {
    parsedUrl = new URL(url);
  } catch {
    throw new Error(`Invalid URL: ${url}`);
  }

  if (parsedUrl.username || parsedUrl.password) {
    throw new Error("URLs with embedded credentials are not supported");
  }
  if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
    throw new Error("URL must use http or https");
  }

  return parsedUrl;
}

function canonicalizeUrl(url) {
  const canonicalUrl = new URL(url.href);
  canonicalUrl.protocol = canonicalUrl.protocol.toLowerCase();
  canonicalUrl.hostname = canonicalUrl.hostname.toLowerCase();
  canonicalUrl.hash = "";
  if ((canonicalUrl.protocol === "http:" && canonicalUrl.port === "80") ||
      (canonicalUrl.protocol === "https:" && canonicalUrl.port === "443")) {
    canonicalUrl.port = "";
  }
  if (!canonicalUrl.pathname) canonicalUrl.pathname = "/";
  return canonicalUrl.href;
}

function formatTimestamp(date) {
  const twoDigits = (value) => String(value).padStart(2, "0");
  return `${String(date.getFullYear()).slice(-2)}${twoDigits(date.getMonth() + 1)}${twoDigits(date.getDate())}-${twoDigits(date.getHours())}-${twoDigits(date.getMinutes())}`;
}

function createRunHash(url) {
  return createHash("sha256")
    .update(`${RUN_NAME_VERSION}\n${canonicalizeUrl(url)}`)
    .digest("hex")
    .slice(0, RUN_HASH_LENGTH);
}

function createRunName(url, date = new Date()) {
  const host = url.hostname.replace(/[^a-zA-Z0-9-]+/g, "-");
  let decodedPath = url.pathname;
  try {
    decodedPath = decodeURIComponent(decodedPath);
  } catch {
    // Keep the original escaped path if it contains malformed percent encoding.
  }
  const path = decodedPath
    .replace(/^\/+|\/+$/g, "")
    .replace(/[^a-zA-Z0-9-]+/g, "-");
  const label = [host, path].filter(Boolean).join("-").slice(0, URL_LABEL_MAX_LENGTH);
  const hash = createRunHash(url);

  return [formatTimestamp(date), label || "page", hash].join("-");
}

function getArtifactDir(options) {
  if (options.outputDir) return resolve(options.outputDir);
  return DEFAULT_TASKS_DIR;
}

function getEvidenceDir() {
  return DEFAULT_EVIDENCE_DIR;
}

function getArtifactExtension(format) {
  return format === "html" ? "html" : "md";
}

async function createArtifactPath(directory, name, extension) {
  await mkdir(directory, { recursive: true });
  let suffix = 1;
  while (true) {
    const collision = suffix === 1 ? "" : `-n${suffix}`;
    const path = join(directory, `${name}${collision}.${extension}`);
    try {
      await writeFile(path, "", { encoding: "utf8", flag: "wx" });
      return path;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      suffix += 1;
    }
  }
}

async function prepareArtifacts(options, parsedUrl) {
  const name = createRunName(parsedUrl);
  const evidenceDir = getEvidenceDir();
  await mkdir(evidenceDir, { recursive: true });

  if (options.outPath) {
    const outputPath = resolve(options.outPath);
    await mkdir(dirname(outputPath), { recursive: true });
    const reservationPath = await createArtifactPath(evidenceDir, name, "reservation");
    return {
      outputPath,
      evidenceDir,
      evidenceStem: reservationPath.slice(0, -".reservation".length),
      reservationPath,
    };
  }

  const extension = getArtifactExtension(options.format);
  const artifactDir = getArtifactDir(options);
  await mkdir(artifactDir, { recursive: true });
  while (true) {
    const reservationPath = await createArtifactPath(evidenceDir, name, "reservation");
    const outputStem = basename(reservationPath, ".reservation");
    const outputPath = join(artifactDir, `${outputStem}.${extension}`);
    try {
      await writeFile(outputPath, "", { encoding: "utf8", flag: "wx" });
      return {
        outputPath,
        evidenceDir,
        evidenceStem: join(evidenceDir, outputStem),
        reservationPath,
      };
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
    }
  }
}

function validateOptions(options) {
  const waitUntilValues = new Set(["load", "domcontentloaded", "networkidle"]);

  if (!waitUntilValues.has(options.waitUntil)) {
    throw new Error("--wait-until must be load, domcontentloaded, or networkidle");
  }
}

async function assertStateFileReadable(statePath) {
  if (!statePath) return;
  const resolved = resolve(statePath);
  try {
    await access(resolved);
  } catch {
    throw new Error(`--state file not found: ${resolved}`);
  }
}

function stateMatchesHost(state, host) {
  return state.cookies?.some((cookie) => {
    const domain = (cookie.domain || "").replace(/^\./, "").toLowerCase();
    return domain && (host === domain || host.endsWith(`.${domain}`));
  }) || state.origins?.some((origin) => {
    try {
      return new URL(origin.origin).hostname.toLowerCase() === host;
    } catch {
      return false;
    }
  });
}

async function findReusableState(parsedUrl, stateDir = DEFAULT_STATE_DIR) {
  let names;
  try {
    names = await readdir(stateDir);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }

  const candidates = await Promise.all(names
    .filter((name) => name.endsWith(".json"))
    .map(async (name) => {
      const path = join(stateDir, name);
      try {
        const [content, metadata] = await Promise.all([readFile(path, "utf8"), stat(path)]);
        const state = JSON.parse(content);
        if (!stateMatchesHost(state, parsedUrl.hostname)) return null;
        return { path, modifiedMs: metadata.mtimeMs };
      } catch {
        return null;
      }
    }));

  return candidates
    .filter(Boolean)
    .sort((left, right) => right.modifiedMs - left.modifiedMs)[0]?.path ?? null;
}

async function resolveStatePath(options, parsedUrl) {
  if (options.statePath) {
    await assertStateFileReadable(options.statePath);
    return options.statePath;
  }

  const statePath = await findReusableState(parsedUrl);
  if (statePath) {
    console.error(`[webfetch-plus] Reusing matching session state from ${statePath}`);
  }
  return statePath;
}

async function loadCloakBrowser() {
  try {
    const modulePath = join(DEPENDENCY_ROOT, "node_modules", "cloakbrowser", "dist", "index.js");
    return await import(pathToFileURL(modulePath).href);
  } catch (error) {
    throw new Error(
      `Cannot load cloakbrowser. Run: npm install --prefix "${DEPENDENCY_ROOT}"\n${error.message}`,
    );
  }
}

async function resolveChromeBinary(stealth) {
  if (process.env.CLOAKBROWSER_BINARY_PATH) return process.env.CLOAKBROWSER_BINARY_PATH;
  if (process.env.CLOAKBROWSER_DOWNLOAD_URL) return null;
  if (stealth) return null;

  const { execSync } = await import("node:child_process");
  const { stat } = await import("node:fs/promises");

  const finders = {
    darwin: async (name) => {
      const result = execSync(`mdfind 'kMDItemDisplayName == "${name}"'`, { encoding: "utf8", timeout: 5000 }).trim();
      if (!result) return null;
      const path = `${result}/Contents/MacOS/${name}`;
      await stat(path);
      return path;
    },
    linux: (cmd) => execSync(`which ${cmd}`, { encoding: "utf8", timeout: 3000 }).trim().split("\n")[0],
    win32: (cmd) => execSync(`where ${cmd}`, { encoding: "utf8", timeout: 3000 }).trim().split("\n")[0],
  };

  const candidates = {
    darwin: ["Google Chrome", "Chromium", "Microsoft Edge", "Brave Browser"],
    linux: ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave", "microsoft-edge"],
    win32: ["chrome", "msedge", "brave"],
  };

  const platform = process.platform;
  const finder = finders[platform];
  if (!finder) return null;

  for (const candidate of candidates[platform]) {
    try {
      const path = await finder(candidate);
      if (path) {
        console.error(`[webfetch-plus] Found local browser: ${path}`);
        return path;
      }
    } catch {
      continue;
    }
  }

  console.error("[webfetch-plus] No local Chrome found, will use CloakBrowser's patched Chromium (~100MB)");
  return null;
}

function getBrowserLaunchOptions(options) {
  const headed = options.visible || options.humanChallenge;
  const args = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    "--disable-features=Translate,MediaRouter,OptimizationHints",
  ];
  // headed 人工挑战时保留窗口，便于拖滑块
  if (!headed) args.splice(2, 0, "--no-startup-window");

  return {
    headless: !headed,
    args,
  };
}

async function waitForPage(page, waitMs) {
  if (waitMs === 0) return;

  if (typeof page.waitForTimeout === "function") {
    await page.waitForTimeout(waitMs);
    return;
  }

  await new Promise((resolve) => setTimeout(resolve, waitMs));
}

async function extractPage(page, selector, format) {
  const pageData = await page.evaluate(
    ({ selector, format }) => {
      const root = selector ? document.querySelector(selector) : document.body;

      if (!root) {
        return {
          error: `Selector not found: ${selector}`,
          url: location.href,
          title: document.title,
        };
      }

      if (format === "html") {
        return {
          url: location.href,
          title: document.title.trim(),
          html: root.innerHTML.trim(),
        };
      }

      const clone = root.cloneNode(true);
      clone
        .querySelectorAll(
          "script,style,noscript,template,svg,canvas,iframe,form,button,input,select,textarea",
        )
        .forEach((element) => element.remove());

      const description =
        document.querySelector('meta[name="description"]')?.content?.trim() ||
        document.querySelector('meta[property="og:description"]')?.content?.trim() ||
        "";

      const text = (clone.innerText || clone.textContent || "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .join("\n");

      return {
        url: location.href,
        title: document.title.trim(),
        description,
        text,
      };
    },
    { selector, format },
  );

  return pageData;
}

async function collectEvidence(page, selector, error, response, options = {}) {
  const base = {
    ok: false,
    error: error.message,
    status: response?.status?.() ?? null,
    statusText: response?.statusText?.() ?? null,
    finalUrl: page.url(),
    selector,
  };

  let html = "";
  let metadata;

  try {
    html = await page.content();
    metadata = await page.evaluate(
      ({ selector }) => {
        const root = selector ? document.querySelector(selector) : document.body;
        return {
          finalUrl: location.href,
          title: document.title.trim(),
          htmlLength: root?.innerHTML?.length ?? document.documentElement.outerHTML.length,
          textLength: (root?.innerText || root?.textContent || "").trim().length,
        };
      },
      { selector },
    );
    metadata = { ...base, ...metadata };
  } catch {
    metadata = { ...base, title: "", htmlLength: 0, textLength: 0 };
  }

  metadata.suggestion = inferSuggestion({
    ...metadata,
    html,
    requestedUrl: options.url,
    stealth: Boolean(options.stealth),
  });
  return { html, metadata };
}

const WAF_SIGNATURES = [
  { name: "Cloudflare", patterns: ["just a moment", "cloudflare", "cf-ray", "__cf_bm", "attention required", "challenges.cloudflare.com", "__cf_chl"] },
  { name: "DataDome", patterns: ["blocked by datadome", "captcha-delivery.com", "dd-cookie", "datadome"] },
  { name: "Akamai", patterns: ["reference #18", "akamai", "akamai-bot-manager"] },
  { name: "PerimeterX", patterns: ["human verification", "_px", "perimeterx", "px-captcha"] },
  { name: "Imperva", patterns: ["incapsula", "_incapsula_resource", "visid_incap"] },
  { name: "F5/Distil", patterns: ["pardon our interruption", "distil", "d_rid"] },
  { name: "Kasada", patterns: ["ips.js", "x-kpsdk", "kasada"] },
  { name: "AWS WAF", patterns: ["aws-waf-token", "awswaf", "request blocked"] },
  { name: "Sucuri", patterns: ["sucuri", "x-sucuri-id", "cloudproxy"] },
  { name: "Aliyun WAF", patterns: ["cf_app_waf", "alicdn.com/captcha", "waf-nc", "aliyun captcha", "滑动验证"] },
  {
    name: "Baidu Security",
    patterns: [
      "百度安全验证",
      "baidu security",
      "拖动左侧滑块",
      "请完成下方验证",
      "图片未转正",
      "安全提示您当前的操作存在风险",
    ],
  },
];
const HOLLOW_TEXT_LIMIT = 80;
const HOLLOW_HTML_MIN = 1000;
const MIN_REAL_PAGE_TEXT_LENGTH = 200;
const BAIDU_DOM_FINGERPRINTS = ["passmod_puzzle", "passmod_puzzle-wrapper", "passmod_slider"];
function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\\"'\\\"'")}'`;
}

function getDefaultStatePath(targetUrl) {
  try {
    const hostname = new URL(targetUrl).hostname;
    const host = hostname.replace(/[^a-zA-Z0-9-]+/g, "-") || "site";
    return join(DEFAULT_STATE_DIR, `${host}.json`);
  } catch {
    return join(DEFAULT_STATE_DIR, "site.json");
  }
}

function createHumanChallengeHint(targetUrl = "<url>") {
  const quotedUrl = targetUrl === "<url>" ? "'<url>'" : shellQuote(targetUrl);
  return `Run this in an interactive TTY (do not pipe): bash bin/wfp-human.sh ${quotedUrl}`;
}

function detectWaf(context) {
  const textHaystack = [context.error, context.finalUrl, context.title, context.text]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
  const htmlHaystack = (context.html || "").toLowerCase();
  const fullHaystack = `${textHaystack}\n${htmlHaystack}`;
  const title = (context.title || "").trim();
  const looksLikeRealPage = Boolean(title) && pageTextLength(context) >= HOLLOW_TEXT_LIMIT;

  // 百度模板可能残留验证文案；足量正文才可视为真实页面
  const baiduVendor = WAF_SIGNATURES.find((entry) => entry.name === "Baidu Security");
  const hasBaiduText = baiduVendor?.patterns.some((pattern) => textHaystack.includes(pattern.toLowerCase()));
  if (hasBaiduText && (!title || pageTextLength(context) < MIN_REAL_PAGE_TEXT_LENGTH)) {
    return "Baidu Security";
  }

  const otherVendor = WAF_SIGNATURES.find(
    (entry) => entry.name !== "Baidu Security"
      && entry.patterns.some((pattern) => fullHaystack.includes(pattern)),
  );
  if (otherVendor) return otherVendor.name;

  // 真实页面的脚本配置可能含 captcha/robot 字样，不应误判为拦截页
  if (looksLikeRealPage) return null;

  // passMod CSS 残留：仅标题空且正文空壳时才拦截
  const hasBaiduDom = BAIDU_DOM_FINGERPRINTS.some((pattern) => htmlHaystack.includes(pattern));
  if (hasBaiduDom && !title && pageTextLength(context) < HOLLOW_TEXT_LIMIT) {
    return "Baidu Security";
  }

  if (context.status === 403 || context.status === 429 || fullHaystack.includes("access denied")) return "WAF";
  if (fullHaystack.includes("captcha") || fullHaystack.includes("robot")) return "Captcha";
  return null;
}

function pageTextLength(pageData) {
  if (Number.isFinite(pageData.textLength)) return pageData.textLength;
  return (pageData.text || "").trim().length;
}

function pageHtmlLength(pageData) {
  if (Number.isFinite(pageData.htmlLength)) return pageData.htmlLength;
  return (pageData.html || "").length;
}

/** 空标题 + 极短正文 + 大 HTML：常见于验证码骨架未抽到文案 */
function isHollowChallengePage(pageData) {
  const title = (pageData.title || "").trim();
  if (title) return false;
  return pageTextLength(pageData) < HOLLOW_TEXT_LIMIT && pageHtmlLength(pageData) >= HOLLOW_HTML_MIN;
}

function inferSuggestion(context) {
  const { error = "", finalUrl = "", requestedUrl = finalUrl, title = "", html = "", stealth = false } = context;
  const textLength = pageTextLength(context);

  if (error.includes("Selector not found")) {
    return "Next time: use --selector with a stable content node from the HTML.";
  }

  const wafVendor = detectWaf(context);
  if (wafVendor) {
    if (stealth) {
      return `${wafVendor} detected after stealth. ${createHumanChallengeHint(requestedUrl)}.`;
    }
    return `${wafVendor} detected. Remaining retries auto-use --stealth; if still blocked: ${createHumanChallengeHint(requestedUrl)}.`;
  }

  if (error.includes("Timeout") || error.includes("timeout")) {
    return "Next time: add --wait-until domcontentloaded; if still failing, increase --timeout.";
  }

  if (/\/login|\/signin|\/sign-in/.test(finalUrl) || /login|sign in/i.test(title)) {
    return `Next time: initialize the session interactively with ${createHumanChallengeHint(requestedUrl)}.`;
  }

  if (isHollowChallengePage(context)) {
    return `Page content too thin. Try --wait 3000, or if a captcha is shown: ${createHumanChallengeHint(requestedUrl)}.`;
  }

  if (textLength === 0 && html.length > 0) {
    return "Page loaded but empty text. Try --wait 3000 for lazy-loaded content.";
  }

  return "Next time: narrow --selector; if HTML itself is abnormal, adjust loading and session params.";
}

function getWafVendor(pageData) {
  return detectWaf(pageData);
}

function isWafPage(pageData) {
  return getWafVendor(pageData) !== null;
}

/** Node stdin 用 readable，不是 isReadable */
function canUseHumanChallengeInput(stdin = process.stdin) {
  return Boolean(stdin?.isTTY && stdin?.readable);
}

async function waitForHumanEnter(vendor, timeoutMs) {
  if (!canUseHumanChallengeInput()) {
    return {
      ok: false,
      status: "non-tty",
      error: "Human verification requires an interactive TTY; use argument form, not echo|pipe",
    };
  }
  process.stderr.write(`[webfetch-plus] ${vendor} detected. Complete verification in the browser, then press Enter.\n`);
  const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
  let timer;
  try {
    const answer = await Promise.race([
      new Promise((resolve) => rl.question("[webfetch-plus] Press Enter after verification: ", resolve)),
      new Promise((resolve) => { timer = setTimeout(() => resolve(null), timeoutMs); }),
    ]);
    if (answer === null) return { ok: false, status: "timeout", error: `Human verification timed out after ${timeoutMs}ms` };
    return { ok: true, status: "completed" };
  } catch (error) {
    return { ok: false, status: "eof", error: `Human verification input failed: ${error.message}` };
  } finally {
    if (timer) clearTimeout(timer);
    rl.close();
  }
}

async function tryExtractOutput(page, options) {
  const pageData = await extractPage(page, options.selector, options.format);
  const html = typeof page.content === "function" ? await page.content() : pageData.html || "";
  const output = renderPage({ ...pageData, html }, options.format);
  return { output, pageData, html };
}

/** 同页多次回车；过关后重新导航（带上验证 cookie），避免抽到残留验证码 DOM */
async function completeHumanChallenge(page, vendor, options) {
  const deadline = Date.now() + options.humanTimeoutMs;
  let lastError = "Challenge still present";

  while (Date.now() < deadline) {
    const remaining = Math.max(1, deadline - Date.now());
    const human = await waitForHumanEnter(vendor, remaining);
    if (!human.ok) return human;

    try {
      process.stderr.write("[webfetch-plus] Reloading target URL with challenge cookies...\n");
      await page.goto(options.url, {
        waitUntil: options.waitUntil,
        timeout: options.timeoutMs,
      });
      await waitForPage(page, Math.max(options.waitMs, HUMAN_POST_WAIT_MS));
      const extracted = await tryExtractOutput(page, options);
      return { ok: true, status: "completed", ...extracted };
    } catch (error) {
      lastError = error.message;
      const html = typeof page.content === "function" ? await page.content() : "";
      const pageData = await extractPage(page, options.selector, options.format).catch(() => ({ title: "", text: "" }));
      if (!detectWaf({ ...pageData, html, error: error.message }) && !/too thin/i.test(error.message)) {
        return { ok: false, status: "challenge-remains", error: lastError };
      }
      process.stderr.write(
        `[webfetch-plus] Challenge still present (${lastError}). ` +
          "Confirm the author page is visible (not the slider), then press Enter again.\n",
      );
    }
  }

  return { ok: false, status: "timeout", error: `Human verification timed out: ${lastError}` };
}

function renderPage(pageData, format) {
  if (pageData.error) {
    throw new Error(pageData.error);
  }

  const wafVendor = getWafVendor(pageData);
  if (wafVendor) {
    throw new Error(`${wafVendor} blocked: ${pageData.title || "untitled page"}`);
  }

  if (isHollowChallengePage(pageData)) {
    throw new Error("Page content too thin; possible challenge or incomplete load");
  }

  if (format === "html") {
    return pageData.html;
  }

  if (format === "text") {
    return [pageData.title, pageData.url, pageData.description, pageData.text]
      .filter(Boolean)
      .join("\n\n");
  }

  if (format !== "markdown") {
    throw new Error(`Unsupported format: ${format}`);
  }

  const title = pageData.title || "Untitled";
  return [`# ${title}`, `Source: ${pageData.url}`, pageData.description, pageData.text]
    .filter(Boolean)
    .join("\n\n");
}

async function writeEvidence(stem, attempt, evidence) {
  const prefix = `${stem}-attempt-${attempt}`;
  const metadataPath = `${prefix}.metadata.json`;
  const htmlPath = `${prefix}.html`;

  await writeFile(metadataPath, `${JSON.stringify(evidence.metadata, null, 2)}\n`, "utf8");
  await writeFile(htmlPath, evidence.html, "utf8");

  return { metadataPath, htmlPath };
}

async function openBrowserContext(browser, options) {
  if (typeof browser.newContext !== "function") {
    return { context: browser, ownsContext: false };
  }
  const contextOptions = {};
  if (options.statePath) {
    contextOptions.storageState = resolve(options.statePath);
    console.error(`[webfetch-plus] Loading session state from ${contextOptions.storageState}`);
  }
  const context = await browser.newContext(contextOptions);
  return { context, ownsContext: true };
}

async function maybeSaveState(context, options) {
  if (!options.saveStatePath) return null;
  if (typeof context.storageState !== "function") {
    throw new Error("--save-state requires browser.newContext().storageState()");
  }
  const savePath = resolve(options.saveStatePath);
  await mkdir(dirname(savePath), { recursive: true });
  await context.storageState({ path: savePath });
  console.error(`[webfetch-plus] Saved session state to ${savePath}`);
  return savePath;
}

async function deliverSuccess(finalOutPath, output, context, options) {
  await writeFile(finalOutPath, output, "utf8");
  await maybeSaveState(context, options);
  process.stdout.write(`${finalOutPath}\n`);
}

async function removeReservation(reservationPath, succeeded) {
  if (!reservationPath) return;
  if (!succeeded) return;
  await rm(reservationPath, { force: true });
}

async function fetchOnce(context, options) {
  const page = await context.newPage();
  let response = null;

  try {
    response = await page.goto(options.url, {
      waitUntil: options.waitUntil,
      timeout: options.timeoutMs,
    });
    await waitForPage(page, options.waitMs);

    const extracted = await tryExtractOutput(page, options);
    return { ...extracted, page, response };
  } catch (error) {
    return { error, page, response };
  }
}

async function launchBrowser(launch, options) {
  if (options.stealth && !process.env.CLOAKBROWSER_CACHE_DIR) {
    process.env.CLOAKBROWSER_CACHE_DIR = join(RUNTIME_ROOT, "browser");
  }
  if (options.stealth) {
    console.error("[webfetch-plus] Using stealth mode with CloakBrowser's patched Chromium (runtime/browser)");
  }

  const localBinary = await resolveChromeBinary(options.stealth);
  let configuredBinary = false;
  if (localBinary && !process.env.CLOAKBROWSER_BINARY_PATH) {
    process.env.CLOAKBROWSER_BINARY_PATH = localBinary;
    configuredBinary = true;
  }
  return { browser: await launch(getBrowserLaunchOptions(options)), configuredBinary };
}

async function main() {
  const options = parseArgs(process.argv);
  validateOptions(options);
  const parsedUrl = normalizeUrl(options.url);
  options.statePath = await resolveStatePath(options, parsedUrl);
  const artifacts = await prepareArtifacts(options, parsedUrl);
  const finalOutPath = artifacts.outputPath;
  const { launch } = await loadCloakBrowser();

  await mkdir(dirname(finalOutPath), { recursive: true });

  let activeOptions = { ...options };
  let launchResult = await launchBrowser(launch, activeOptions);
  let browser = launchResult.browser;
  let configuredBinary = launchResult.configuredBinary;
  let session = await openBrowserContext(browser, activeOptions);
  let succeeded = false;
  try {
    const failures = [];

    for (let attempt = 1; attempt <= options.retries; attempt += 1) {
      const result = await fetchOnce(session.context, activeOptions);

      if (result.output) {
        await deliverSuccess(finalOutPath, result.output, session.context, activeOptions);
        succeeded = true;
        await result.page.close();
        return;
      }

      const evidence = await collectEvidence(
        result.page,
        activeOptions.selector,
        result.error,
        result.response,
        activeOptions,
      );
      const evidencePaths = await writeEvidence(artifacts.evidenceStem, attempt, evidence);
      const wafVendor = detectWaf({
        ...evidence.metadata,
        html: evidence.html,
        error: result.error.message,
      });
      const suggestion = inferSuggestion({
        ...evidence.metadata,
        html: evidence.html,
        error: result.error.message,
        requestedUrl: activeOptions.url,
        stealth: activeOptions.stealth,
      });
      failures.push({
        attempt,
        stealth: activeOptions.stealth,
        wafVendor,
        error: result.error.message,
        suggestion,
        ...evidencePaths,
      });

      if (wafVendor && activeOptions.humanChallenge) {
        const human = await completeHumanChallenge(result.page, wafVendor, activeOptions);
        failures[failures.length - 1].human = {
          ok: human.ok,
          status: human.status,
          error: human.error,
        };
        if (human.ok && human.output) {
          await deliverSuccess(finalOutPath, human.output, session.context, activeOptions);
          succeeded = true;
          await result.page.close();
          return;
        }
      }
      await result.page.close();

      if (wafVendor && !activeOptions.stealth && attempt < options.retries) {
        console.error(`[webfetch-plus] ${wafVendor} detected; retrying with --stealth`);
        if (session.ownsContext) await session.context.close();
        await browser.close();
        if (configuredBinary) delete process.env.CLOAKBROWSER_BINARY_PATH;
        activeOptions = { ...options, stealth: true };
        launchResult = await launchBrowser(launch, activeOptions);
        browser = launchResult.browser;
        configuredBinary = launchResult.configuredBinary;
        session = await openBrowserContext(browser, activeOptions);
      }
    }

    const failurePath = `${artifacts.evidenceStem}-failure-summary.json`;
    await writeFile(failurePath, `${JSON.stringify({ ok: false, failures }, null, 2)}\n`, "utf8");
    const wafFailure = failures.find((failure) => failure.wafVendor);
    const sessionHint = wafFailure && !options.statePath
      ? ` No matching saved session was available. ${createHumanChallengeHint(options.url)}.`
      : "";
    throw new Error(`All attempts failed.${sessionHint} Evidence: ${failurePath}`);
  } finally {
    if (session?.ownsContext) {
      try { await session.context.close(); } catch { /* browser may already be closed */ }
    }
    await browser.close();
    if (configuredBinary) delete process.env.CLOAKBROWSER_BINARY_PATH;
    await removeReservation(artifacts.reservationPath, succeeded);
    if (!succeeded) {
      await rm(finalOutPath, { force: true });
    }
  }
}

if (process.argv[1] === SCRIPT_PATH) {
  main().catch((error) => {
    console.error(`webfetch-plus failed: ${error.message}`);
    process.exit(1);
  });
}

export {
  canonicalizeUrl,
  canUseHumanChallengeInput,
  createArtifactPath,
  createRunHash,
  createRunName,
  detectWaf,
  getArtifactDir,
  getDefaultStatePath,
  inferSuggestion,
  isHollowChallengePage,
  findReusableState,
  normalizeUrl,
  prepareArtifacts,
  renderPage,
};
