#!/usr/bin/env node

import { mkdir, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
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
]);
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SKILL_ROOT = resolve(process.env.WFP_PATH ?? dirname(SCRIPT_PATH), process.env.WFP_PATH ? "." : "..");
const RUNTIME_ROOT = join(SKILL_ROOT, "runtime");
const DEPENDENCY_ROOT = join(RUNTIME_ROOT, "node");
const DEFAULT_TASKS_DIR = "/tmp/wfp-tasks";
const DEFAULT_EVIDENCE_DIR = "/tmp/wfp-evidence";
const EVIDENCE_DIR_NAME = "webfetch-plus-evidence";
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
`);
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
  };
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

function getEvidenceDir(options) {
  if (options.outputDir) return join(getArtifactDir(options), EVIDENCE_DIR_NAME);
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
  const evidenceDir = getEvidenceDir(options);
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
        console.log(`[webfetch-plus] Found local browser: ${path}`);
        return path;
      }
    } catch {
      continue;
    }
  }

  console.log("[webfetch-plus] No local Chrome found, will use CloakBrowser's patched Chromium (~100MB)");
  return null;
}

function getBrowserLaunchOptions(options) {
  return {
    headless: !options.visible,
    args: [
      "--no-first-run",
      "--no-default-browser-check",
      "--no-startup-window",
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-sync",
      "--disable-features=Translate,MediaRouter,OptimizationHints",
    ],
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

async function collectEvidence(page, selector, error, response) {
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

  metadata.suggestion = inferSuggestion({ ...metadata, html });
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
  { name: "Baidu Security", patterns: ["百度安全验证", "拖动左侧滑块", "图片未转正", "安全提示您当前的操作存在风险"] },
];

function detectWaf(context) {
  const haystack = [context.error, context.finalUrl, context.title, context.text, context.html]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
  const vendor = WAF_SIGNATURES.find(({ patterns }) => patterns.some((pattern) => haystack.includes(pattern)));
  if (vendor) return vendor.name;
  if (context.status === 403 || context.status === 429 || haystack.includes("access denied")) return "WAF";
  if (haystack.includes("captcha") || haystack.includes("robot")) return "Captcha";
  return null;
}

function inferSuggestion(context) {
  const { error, finalUrl, title, html, textLength } = context;

  if (error.includes("Selector not found")) {
    return "Next time: use --selector with a stable content node from the HTML.";
  }

  const wafVendor = detectWaf(context);
  if (wafVendor) {
    return `${wafVendor} detected. The next retry automatically uses --stealth when available.`;
  }

  if (error.includes("Timeout") || error.includes("timeout")) {
    return "Next time: add --wait-until domcontentloaded; if still failing, increase --timeout.";
  }

  if (/\/login|\/signin|\/sign-in/.test(finalUrl) || /login|sign in/i.test(title)) {
    return "Next time: add --profile <name> --save-state to reuse login or popup state.";
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

function renderPage(pageData, format) {
  if (pageData.error) {
    throw new Error(pageData.error);
  }

  const wafVendor = getWafVendor(pageData);
  if (wafVendor) {
    throw new Error(`${wafVendor} blocked: ${pageData.title || "untitled page"}`);
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

async function fetchOnce(browser, options) {
  const page = await browser.newPage();
  let response = null;

  try {
    response = await page.goto(options.url, {
      waitUntil: options.waitUntil,
      timeout: options.timeoutMs,
    });
    await waitForPage(page, options.waitMs);

    const pageData = await extractPage(page, options.selector, options.format);
    const output = renderPage(pageData, options.format);
    return { output, page, response };
  } catch (error) {
    return { error, page, response };
  }
}

async function launchBrowser(launch, options) {
  if (options.stealth && !process.env.CLOAKBROWSER_CACHE_DIR) {
    process.env.CLOAKBROWSER_CACHE_DIR = join(RUNTIME_ROOT, "browser");
  }
  if (options.stealth) {
    console.log("[webfetch-plus] Using stealth mode with CloakBrowser's patched Chromium (runtime/browser)");
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
  const artifacts = await prepareArtifacts(options, parsedUrl);
  const finalOutPath = artifacts.outputPath;
  const { launch } = await loadCloakBrowser();

  await mkdir(dirname(finalOutPath), { recursive: true });

  let activeOptions = { ...options };
  let launchResult = await launchBrowser(launch, activeOptions);
  let browser = launchResult.browser;
  let configuredBinary = launchResult.configuredBinary;
  let succeeded = false;
  try {
    const failures = [];

    for (let attempt = 1; attempt <= options.retries; attempt += 1) {
      const result = await fetchOnce(browser, activeOptions);

      if (result.output) {
        await writeFile(finalOutPath, result.output, "utf8");
        succeeded = true;
        process.stdout.write(`${finalOutPath}\n`);
        return;
      }

      const evidence = await collectEvidence(result.page, activeOptions.selector, result.error, result.response);
      const evidencePaths = await writeEvidence(artifacts.evidenceStem, attempt, evidence);
      const wafVendor = detectWaf({ ...evidence.metadata, html: evidence.html });
      failures.push({
        attempt,
        stealth: activeOptions.stealth,
        error: result.error.message,
        suggestion: evidence.metadata.suggestion,
        ...evidencePaths,
      });
      await result.page.close();

      if (wafVendor && !activeOptions.stealth && attempt < options.retries) {
        console.log(`[webfetch-plus] ${wafVendor} detected; retrying with --stealth`);
        await browser.close();
        if (configuredBinary) delete process.env.CLOAKBROWSER_BINARY_PATH;
        activeOptions = { ...options, stealth: true };
        launchResult = await launchBrowser(launch, activeOptions);
        browser = launchResult.browser;
        configuredBinary = launchResult.configuredBinary;
      }
    }

    const failurePath = `${artifacts.evidenceStem}-failure-summary.json`;
    await writeFile(failurePath, `${JSON.stringify({ ok: false, failures }, null, 2)}\n`, "utf8");
    throw new Error(`All attempts failed. Evidence: ${failurePath}`);
  } finally {
    await browser.close();
    if (configuredBinary) delete process.env.CLOAKBROWSER_BINARY_PATH;
    if (artifacts.reservationPath && succeeded) {
      await rm(artifacts.reservationPath, { force: true });
    } else if (!succeeded && !artifacts.reservationPath) {
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
  createArtifactPath,
  createRunHash,
  createRunName,
  getArtifactDir,
  normalizeUrl,
  prepareArtifacts,
};
