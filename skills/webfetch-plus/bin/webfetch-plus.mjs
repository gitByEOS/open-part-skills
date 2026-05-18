#!/usr/bin/env node

import { mkdir, rm, writeFile, readdir, unlink } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import process from "node:process";

const DEFAULT_TIMEOUT_MS = 45_000;
const DEFAULT_RETRIES = 3;
const MAX_RETRIES = 3;
const BOOLEAN_OPTIONS = new Set(["--archive", "--visible"]);
const OPTION_NAMES_WITH_VALUES = new Set([
  "--out",
  "--output-dir",
  "--wait",
  "--timeout",
  "--wait-until",
  "--retries",
  "--selector",
  "--format",
  "--task",
]);
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SKILL_ROOT = resolve(process.env.WFP_PATH ?? dirname(SCRIPT_PATH), process.env.WFP_PATH ? "." : "..");
const RUNTIME_ROOT = join(SKILL_ROOT, "runtime");
const DEPENDENCY_ROOT = join(RUNTIME_ROOT, "node");
const DEFAULT_CURRENT_DIR = join(RUNTIME_ROOT, "current");
const DEFAULT_ARCHIVE_DIR = join(RUNTIME_ROOT, "runs");

function printUsage() {
  console.error(`Usage:
  WFP_PATH=.cursor/skills/webfetch-plus
  cd "$WFP_PATH" && node bin/webfetch-plus.mjs <url> [options]

Options:
  --out <path>             Write output to a file
  --output-dir <path>      Write output into a custom directory
  --archive                Keep this run under runtime/runs instead of overwriting runtime/current
  --visible                Show browser window; default is hidden/headless
  --wait <ms>              Wait after navigation before extraction
  --timeout <ms>           Navigation timeout, default ${DEFAULT_TIMEOUT_MS}
  --wait-until <state>     load, domcontentloaded, networkidle; default networkidle
  --retries <1-3>          Max attempts, default ${DEFAULT_RETRIES}
  --selector <css>         Extract only a specific CSS selector
  --format <markdown|text|html>
  --task <n>               Task identifier, isolates output files (page_{n}.md, etc.), default 1
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
    archive: options.has("--archive"),
    visible: options.has("--visible"),
    waitMs: readNumberOption(options, "--wait", 0),
    timeoutMs: readNumberOption(options, "--timeout", DEFAULT_TIMEOUT_MS),
    waitUntil: readOption(options, "--wait-until", "networkidle"),
    retries: readIntegerOption(options, "--retries", DEFAULT_RETRIES, MAX_RETRIES),
    selector: readOption(options, "--selector"),
    format: readOption(options, "--format", "markdown"),
    taskId: readOption(options, "--task", "1"),
  };
}

function getCliArgs(argv) {
  const firstArg = argv[1] ?? "";
  const isEvalImport = firstArg.startsWith("http://") || firstArg.startsWith("https://") || firstArg.startsWith("-");

  return argv.slice(isEvalImport ? 1 : 2);
}

function normalizeUrl(url) {
  try {
    return new URL(url);
  } catch {
    throw new Error(`Invalid URL: ${url}`);
  }
}

function formatTimestamp(date) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function createRunName(url) {
  const host = url.hostname.replace(/[^a-zA-Z0-9.-]/g, "-");
  const path = url.pathname
    .replace(/^\/+|\/+$/g, "")
    .replace(/[^a-zA-Z0-9.-]+/g, "-")
    .slice(0, 80);

  return [formatTimestamp(new Date()), host, path].filter(Boolean).join("__");
}

function getRunDir(options, parsedUrl) {
  if (options.outputDir) {
    return resolve(options.outputDir);
  }

  if (options.archive) {
    return join(DEFAULT_ARCHIVE_DIR, createRunName(parsedUrl));
  }

  return DEFAULT_CURRENT_DIR;
}

function getDefaultOutputPath(options) {
  const extension = options.format === "html" ? "html" : "md";
  return join(options.runDir, `page_${options.taskId}.${extension}`);
}

async function cleanTaskFiles(runDir, taskId) {
  try {
    const entries = await readdir(runDir);
    for (const entry of entries) {
      if (entry.includes(taskId) || entry === `page_${taskId}.md` || entry === `page_${taskId}.html`) {
        await unlink(join(runDir, entry));
      }
    }
  } catch {
    // Directory may not exist yet
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
      `Cannot load cloakbrowser. Run: npm install --prefix .cursor/skills/webfetch-plus/runtime/node\n${error.message}`,
    );
  }
}

async function resolveChromeBinary() {
  if (process.env.CLOAKBROWSER_BINARY_PATH) return process.env.CLOAKBROWSER_BINARY_PATH;
  if (process.env.CLOAKBROWSER_DOWNLOAD_URL) return null;

  const { stat } = await import("node:fs/promises");
  const candidates = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ];

  for (const candidate of candidates) {
    try {
      await stat(candidate);
      console.log(`[webfetch-plus] Found local browser: ${candidate}`);
      return candidate;
    } catch {
      continue;
    }
  }
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
  return page.evaluate(
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
}

async function collectEvidence(page, selector, error, response) {
  let html = "";
  let metadata = {
    ok: false,
    error: error.message,
    status: response?.status?.() ?? null,
    statusText: response?.statusText?.() ?? null,
    finalUrl: page.url(),
    title: "",
    selector,
    htmlLength: 0,
    textLength: 0,
    suggestion: "查看 HTML 和 metadata 后，只增加一个最相关参数。",
  };

  try {
    html = await page.content();
    metadata = await page.evaluate(
      ({ selector, base }) => {
        const root = selector ? document.querySelector(selector) : document.body;
        const title = document.title.trim();
        const text = (root?.innerText || root?.textContent || "").trim();
        const html = root?.innerHTML || document.documentElement.outerHTML || "";

        return {
          ...base,
          finalUrl: location.href,
          title,
          htmlLength: html.length,
          textLength: text.length,
        };
      },
      { selector, base: metadata },
    );
    metadata.suggestion = inferSuggestion(
      metadata.error,
      metadata.status,
      metadata.finalUrl,
      metadata.title,
      html,
      metadata.textLength,
    );
  } catch {
    metadata.suggestion = inferSuggestion(
      metadata.error,
      metadata.status,
      metadata.finalUrl,
      metadata.title,
      html,
      0,
    );
  }

  return { html, metadata };
}

function inferSuggestion(error, status, finalUrl, title, html, textLength) {
  const haystack = `${error}\n${finalUrl}\n${title}\n${html}`.toLowerCase();

  if (error.includes("Selector not found")) {
    return "下一次改：--selector，先用 HTML 里的稳定正文节点。";
  }

  if (error.includes("Timeout") || error.includes("timeout")) {
    return "下一次加：--wait-until domcontentloaded；如果仍失败，再提高 --timeout。";
  }

  if (status === 403 || status === 429 || haystack.includes("access denied")) {
    return "下一次加：--proxy-server；如是地区页，再加 --locale 和 --timezone。";
  }

  if (/\/login|\/signin|\/sign-in/.test(finalUrl) || /login|sign in/i.test(title)) {
    return "下一次加：--profile <name> --save-state，用登录态或弹窗状态复用。";
  }

  if (haystack.includes("captcha") || haystack.includes("cloudflare") || haystack.includes("robot")) {
    return "下一次加：--disable-headless 或 --human，处理挑战页。";
  }

  if (textLength === 0 && html.length > 0) {
    return "下一次加：--wait 3000 或 --scroll，处理懒加载或正文晚到。";
  }

  return "下一次先收窄 --selector；如果 HTML 本身异常，再调整加载和会话参数。";
}

function renderPage(pageData, format) {
  if (pageData.error) {
    throw new Error(pageData.error);
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

async function writeEvidence(runDir, taskId, attempt, evidence) {
  const prefix = join(runDir, `attempt_${taskId}_${attempt}`);
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

async function main() {
  const options = parseArgs(process.argv);
  validateOptions(options);
  const parsedUrl = normalizeUrl(options.url);
  options.runDir = getRunDir(options, parsedUrl);
  const finalOutPath = options.outPath ? resolve(options.outPath) : getDefaultOutputPath(options);
  const { launch } = await loadCloakBrowser();

  const localBinary = await resolveChromeBinary();
  if (localBinary && !process.env.CLOAKBROWSER_BINARY_PATH) {
    process.env.CLOAKBROWSER_BINARY_PATH = localBinary;
  }

  if (!options.outputDir && !options.archive) {
    await cleanTaskFiles(options.runDir, options.taskId);
  }
  await mkdir(dirname(finalOutPath), { recursive: true });
  await mkdir(options.runDir, { recursive: true });

  const browser = await launch(getBrowserLaunchOptions(options));
  try {
    const failures = [];

    for (let attempt = 1; attempt <= options.retries; attempt += 1) {
      const result = await fetchOnce(browser, options);

      if (result.output) {
        await writeFile(finalOutPath, result.output, "utf8");
        process.stdout.write(`${finalOutPath}\n`);
        return;
      }

      const evidence = await collectEvidence(result.page, options.selector, result.error, result.response);
      const evidencePaths = await writeEvidence(options.runDir, options.taskId, attempt, evidence);
      failures.push({
        attempt,
        error: result.error.message,
        suggestion: evidence.metadata.suggestion,
        ...evidencePaths,
      });
      await result.page.close();
    }

    const failurePath = join(options.runDir, `failure_summary_${options.taskId}.json`);
    await writeFile(failurePath, `${JSON.stringify({ ok: false, failures }, null, 2)}\n`, "utf8");
    throw new Error(`All attempts failed. Evidence: ${failurePath}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(`webfetch-plus failed: ${error.message}`);
  process.exit(1);
});
