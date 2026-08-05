import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, utimes, writeFile } from "node:fs/promises";
import { execFile as execFileCallback } from "node:child_process";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { promisify } from "node:util";
import test from "node:test";

const execFile = promisify(execFileCallback);
const RUNTIME_SCRIPT = new URL("./webfetch-plus.mjs", import.meta.url).pathname;
const DEFAULT_TASKS_DIR = "/tmp/wfp-tasks";
const DEFAULT_EVIDENCE_DIR = "/tmp/wfp-evidence";

function formatLocalMinute(date) {
  const twoDigits = (value) => String(value).padStart(2, "0");
  return `${String(date.getFullYear()).slice(-2)}${twoDigits(date.getMonth() + 1)}${twoDigits(date.getDate())}-${twoDigits(date.getHours())}-${twoDigits(date.getMinutes())}`;
}

import {
  canonicalizeUrl,
  canUseHumanChallengeInput,
  createArtifactPath,
  createRunHash,
  createRunName,
  detectWaf,
  findReusableState,
  getArtifactDir,
  getDefaultStatePath,
  inferSuggestion,
  isHollowChallengePage,
  normalizeUrl,
  prepareArtifacts,
  renderPage,
} from "./webfetch-plus.mjs";

test("规范 URL 会移除片段并标准化主机名", () => {
  assert.equal(
    canonicalizeUrl(normalizeUrl("HTTPS://EXAMPLE.COM:443/docs#section")),
    "https://example.com/docs",
  );
  assert.equal(
    createRunHash(normalizeUrl("HTTPS://EXAMPLE.COM:443/docs#section")),
    createRunHash(normalizeUrl("https://example.com/docs")),
  );
});

test("URL 哈希保留查询顺序和百分号编码", () => {
  const first = createRunHash(normalizeUrl("https://example.com/?a=1&b=2"));
  const reordered = createRunHash(normalizeUrl("https://example.com/?b=2&a=1"));
  const encoded = createRunHash(normalizeUrl("https://example.com/%61"));
  const plain = createRunHash(normalizeUrl("https://example.com/a"));

  assert.notEqual(first, reordered);
  assert.notEqual(encoded, plain);
  assert.match(first, /^[a-f0-9]{8}$/);
});

test("产物名采用短时间、URL 标签和短哈希", () => {
  const url = normalizeUrl("https://example.com/a path/?q=1");
  const name = createRunName(url, new Date("2026-08-04T10:23:04.500Z"));

  assert.match(name, new RegExp(`^${formatLocalMinute(new Date("2026-08-04T10:23:04.500Z"))}-example-com-a-path-[a-f0-9]{8}$`));
  assert.throws(() => normalizeUrl("https://user:secret@example.com/"), /embedded credentials/);
});

test("默认和自定义目录直接承载扁平产物", () => {
  assert.equal(getArtifactDir({}), DEFAULT_TASKS_DIR);
  assert.equal(getArtifactDir({ outputDir: "/tmp/wfp-output" }), "/tmp/wfp-output");
});

test("默认会话路径统一由 URL 主机名生成", () => {
  assert.equal(
    getDefaultStatePath("https://Author.Baidu.Com:443/home/123"),
    "/tmp/wfp-states/author-baidu-com.json",
  );
  assert.equal(
    getDefaultStatePath("https://foo..bar---baz.example.com/"),
    "/tmp/wfp-states/foo-bar---baz-example-com.json",
  );
  assert.equal(getDefaultStatePath("not a URL"), "/tmp/wfp-states/site.json");
});

test("自动复用目标域名最新且有效的会话状态", async () => {
  const root = await mkdtemp(join(tmpdir(), "wfp-state-test-"));
  const older = join(root, "older.json");
  const newest = join(root, "newest.json");
  const unrelated = join(root, "unrelated.json");
  const malformed = join(root, "malformed.json");
  try {
    await writeFile(older, JSON.stringify({ cookies: [{ domain: ".baidu.com" }], origins: [] }));
    await writeFile(newest, JSON.stringify({ cookies: [], origins: [{ origin: "https://author.baidu.com" }] }));
    await writeFile(unrelated, JSON.stringify({ cookies: [{ domain: ".example.com" }], origins: [] }));
    await writeFile(malformed, "not json");
    await utimes(older, new Date("2026-08-05T00:00:00Z"), new Date("2026-08-05T00:00:00Z"));
    await utimes(newest, new Date("2026-08-05T00:01:00Z"), new Date("2026-08-05T00:01:00Z"));

    assert.equal(
      await findReusableState(normalizeUrl("https://author.baidu.com/home/123"), root),
      newest,
    );
    assert.equal(await findReusableState(normalizeUrl("https://github.com/"), root), null);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("out 保持请求路径且证据进入默认目录", async () => {
  const root = await mkdtemp(join(tmpdir(), "wfp-out-test-"));
  const outPath = join(root, "result.md");
  try {
    const artifacts = await prepareArtifacts({ outPath, format: "markdown" }, normalizeUrl("https://example.com/page"));
    assert.equal(artifacts.outputPath, outPath);
    assert.match(artifacts.evidenceStem, new RegExp(`^${DEFAULT_EVIDENCE_DIR}/.*-[a-f0-9]{8}$`));
    await rm(artifacts.reservationPath, { force: true });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("同秒同 URL 的扁平产物添加 n 后缀", async () => {
  const parent = await mkdtemp(join(tmpdir(), "wfp-artifact-test-"));
  try {
    const [first, second] = await Promise.all([
      createArtifactPath(parent, "260804-10-23-example-aabbccdd", "md"),
      createArtifactPath(parent, "260804-10-23-example-aabbccdd", "md"),
    ]);
    assert.deepEqual(
      new Set([first, second]),
      new Set([
        join(parent, "260804-10-23-example-aabbccdd.md"),
        join(parent, "260804-10-23-example-aabbccdd-n2.md"),
      ]),
    );
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});

async function createCliFixture() {
  const root = await mkdtemp(join(tmpdir(), "wfp-cli-test-"));
  const modulePath = join(root, "runtime", "node", "node_modules", "cloakbrowser", "dist", "index.js");
  await mkdir(dirname(modulePath), { recursive: true });
  await writeFile(
    modulePath,
    `import { writeFile } from "node:fs/promises";
    let launchCount = 0;
    function createPage(baiduBlocked, hollowPassmod, passmodHtml) {
      return {
        async goto() {
          if (process.env.WFP_TEST_FAILURE === "1") throw new Error("test navigation failure");
          return { status() { return 200; }, statusText() { return "OK"; } };
        },
        async content() {
          if (hollowPassmod) return passmodHtml;
          return baiduBlocked
            ? '<html><body class="passMod_puzzle">百度安全验证 拖动左侧滑块 图片未转正</body></html>'
            : "<html>test page</html>";
        },
        async evaluate(_fn, args) {
          if (process.env.WFP_TEST_RENDER_BAIDU === "1" && args.format) {
            return { error: "Baidu Security blocked", url: "https://author.baidu.com/home/test", title: "", text: "" };
          }
          if (process.env.WFP_TEST_FAILURE === "1") return { title: "", htmlLength: 0, textLength: 0 };
          if (hollowPassmod) {
            return { url: "https://author.baidu.com/home/test", title: "", description: "", text: "" };
          }
          if (baiduBlocked) {
            return {
              url: "https://author.baidu.com/home/test",
              title: "",
              description: "",
              text: "百度安全验证\\n拖动左侧滑块使图片为正\\n图片未转正",
            };
          }
          return { url: "https://example.test/success", title: "Test title", description: "Test description", text: "Test body" };
        },
        url() {
          if (hollowPassmod || baiduBlocked) return "https://author.baidu.com/home/test";
          return "https://example.test/failure";
        },
        async close() {},
      };
    }
    export async function launch() {
      launchCount += 1;
      const alwaysBaidu = process.env.WFP_TEST_BAIDU_ALWAYS === "1";
      const hollowPassmod = process.env.WFP_TEST_HOLLOW_PASSMOD === "1";
      const baiduBlocked = alwaysBaidu || (process.env.WFP_TEST_BAIDU_BLOCKED === "1" && launchCount === 1);
      const passmodHtml = '<html><head></head><body><div class="passMod_puzzle-wrapper"></div>' + "x".repeat(1200) + "</body></html>";
      return {
        async newContext(opts = {}) {
          if (process.env.WFP_TEST_REQUIRE_STATE === "1" && !opts.storageState) {
            throw new Error("storageState required");
          }
          return {
            storageStatePath: opts.storageState || null,
            async newPage() { return createPage(baiduBlocked, hollowPassmod, passmodHtml); },
            async storageState({ path }) {
              await writeFile(path, JSON.stringify({ cookies: [{ name: "wfp", value: "1" }], origins: [] }), "utf8");
            },
            async close() {},
          };
        },
        async newPage() { return createPage(baiduBlocked, hollowPassmod, passmodHtml); },
        async close() {},
      };
    }\n`,
    "utf8",
  );
  return root;
}

function cliEnv(root, extra = {}) {
  return {
    ...process.env,
    WFP_PATH: root,
    CLOAKBROWSER_BINARY_PATH: "/bin/true",
    ...extra,
  };
}

async function runCli(root, args, env = {}) {
  return execFile(
    process.execPath,
    [RUNTIME_SCRIPT, "https://example.test/same", "--retries", "1", ...args],
    { env: cliEnv(root, env) },
  );
}

async function runFailureCli(root, args) {
  try {
    await runCli(root, args, { WFP_TEST_FAILURE: "1" });
    assert.fail("fake browser must make the CLI fail");
  } catch (error) {
    assert.equal(error.code, 1);
    return error;
  }
}

async function runFailureCliAtFixedTime(root, preload, args) {
  try {
    await execFile(
      process.execPath,
      ["--require", preload, RUNTIME_SCRIPT, "https://example.test/same", "--retries", "1", ...args],
      { env: cliEnv(root, { WFP_TEST_FAILURE: "1" }) },
    );
    assert.fail("fake browser must make the CLI fail");
  } catch (error) {
    assert.equal(error.code, 1);
    return error;
  }
}

test("CLI 帮助描述扁平输出契约", async () => {
  const { stderr } = await execFile(process.execPath, [RUNTIME_SCRIPT, "--help"]);

  assert.match(stderr, /--out <path>\s+Write output to this exact path/);
  assert.match(stderr, /--output-dir <path>\s+Write a unique flat output file into this directory/);
  assert.doesNotMatch(stderr, /--archive|--task|--human-challenge|--human-timeout/);
});

test("百度验证码页自动切换 stealth 重试", async () => {
  const root = await createCliFixture();
  try {
    const { stdout, stderr } = await runCli(root, ["--retries", "2"], { WFP_TEST_BAIDU_BLOCKED: "1" });
    assert.match(stderr, /Baidu Security detected; retrying with --stealth/);
    const outputPath = stdout.trim().split("\n").at(-1);
    assert.equal(await readFile(outputPath, "utf8"), "# Test title\n\nSource: https://example.test/success\n\nTest description\n\nTest body");
    await rm(outputPath, { force: true });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("默认成功输出到临时扁平目录", async () => {
  const root = await createCliFixture();
  try {
    const { stdout } = await runCli(root, []);
    const outputPath = stdout.trim();
    assert.match(outputPath, new RegExp(`^${DEFAULT_TASKS_DIR}/\\d{6}-\\d{2}-\\d{2}-.+-[a-f0-9]{8}(?:-n\\d+)?\\.md$`));
    assert.equal(await readFile(outputPath, "utf8"), "# Test title\n\nSource: https://example.test/success\n\nTest description\n\nTest body");
    await rm(outputPath, { force: true });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("output-dir 直接写入唯一正文且 out 保持精确路径", async () => {
  const root = await createCliFixture();
  const outputDir = join(root, "chosen-output");
  const outPath = join(root, "explicit", "result.md");
  try {
    const { stdout: outputDirStdout } = await runCli(root, ["--output-dir", outputDir]);
    assert.match(outputDirStdout.trim(), new RegExp(`^${outputDir}/\\d{6}-\\d{2}-\\d{2}-.+-[a-f0-9]{8}(?:-n\\d+)?\\.md$`));
    const { stdout: outStdout } = await runCli(root, ["--out", outPath]);
    assert.equal(outStdout.trim(), outPath);
    assert.equal(await readFile(outPath, "utf8"), "# Test title\n\nSource: https://example.test/success\n\nTest description\n\nTest body");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("同分钟同 URL 的默认并发调用生成唯一正文", async () => {
  const root = await createCliFixture();
  const preload = join(root, "fixed-time.cjs");
  await writeFile(
    preload,
    `const RealDate = Date; class FixedDate extends RealDate { constructor(...args) { super(...(args.length ? args : ["2026-08-04T11:16:11.000Z"])); } static now() { return new RealDate("2026-08-04T11:16:11.000Z").valueOf(); } } global.Date = FixedDate;\n`,
    "utf8",
  );
  try {
    const run = () => execFile(
      process.execPath,
      ["--require", preload, RUNTIME_SCRIPT, "https://example.test/same", "--retries", "1"],
      { env: cliEnv(root) },
    );
    const [{ stdout: firstStdout }, { stdout: secondStdout }] = await Promise.all([run(), run()]);
    const outputPaths = [firstStdout.trim(), secondStdout.trim()];
    assert.equal(new Set(outputPaths).size, 2);
    for (const outputPath of outputPaths) {
      assert.match(outputPath, new RegExp(`^${DEFAULT_TASKS_DIR}/${formatLocalMinute(new Date("2026-08-04T11:16:11.000Z"))}-.+-[a-f0-9]{8}(?:-n\\d+)?\\.md$`));
      await rm(outputPath, { force: true });
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("默认和 output-dir 并发失败时保留独立证据", async () => {
  const root = await createCliFixture();
  const outputDir = join(root, "chosen-output");
  try {
    const preload = join(root, "fixed-time.cjs");
    await writeFile(
      preload,
      `const RealDate = Date; class FixedDate extends RealDate { constructor(...args) { super(...(args.length ? args : ["2026-08-04T11:16:11.000Z"])); } static now() { return new RealDate("2026-08-04T11:16:11.000Z").valueOf(); } } global.Date = FixedDate;\n`,
      "utf8",
    );
    const failures = await Promise.all([
      runFailureCliAtFixedTime(root, preload, []),
      runFailureCliAtFixedTime(root, preload, ["--output-dir", outputDir]),
    ]);
    const evidencePaths = failures.map((error) => error.stderr.match(/Evidence: (.+)$/m)?.[1]);

    assert.equal(evidencePaths.filter(Boolean).length, 2);
    assert.equal(new Set(evidencePaths).size, 2);
    for (const evidencePath of evidencePaths) {
      assert.match(evidencePath, new RegExp(`^${DEFAULT_EVIDENCE_DIR}/.+-failure-summary\\.json$`));
    }
    for (const evidencePath of evidencePaths) {
      const summary = JSON.parse(await readFile(evidencePath, "utf8"));
      assert.equal(summary.failures.length, 1);
      assert.match(summary.failures[0].metadataPath, /-attempt-1\.metadata\.json$/);
      assert.match(summary.failures[0].htmlPath, /-attempt-1\.html$/);
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("失败证据扁平保存且同秒碰撞不覆盖", async () => {
  const root = await createCliFixture();
  const outputDir = join(root, "chosen-output");
  const preload = join(root, "fixed-time.cjs");
  await writeFile(
    preload,
    `const RealDate = Date; class FixedDate extends RealDate { constructor(...args) { super(...(args.length ? args : ["2026-08-04T11:16:11.000Z"])); } static now() { return new RealDate("2026-08-04T11:16:11.000Z").valueOf(); } } global.Date = FixedDate;\n`,
    "utf8",
  );
  try {
    const failures = await Promise.all([
      runFailureCliAtFixedTime(root, preload, ["--output-dir", outputDir]),
      runFailureCliAtFixedTime(root, preload, ["--output-dir", outputDir]),
    ]);
    for (const error of failures) assert.equal(error.code, 1);
    const evidencePaths = failures.map((error) => error.stderr.match(/Evidence: (.+)$/m)?.[1]);
    assert.equal(new Set(evidencePaths).size, 2);
    for (const evidencePath of evidencePaths) {
      assert.match(evidencePath, new RegExp(`^${DEFAULT_EVIDENCE_DIR}/`));
      const summary = JSON.parse(await readFile(evidencePath, "utf8"));
      assert.match(summary.failures[0].metadataPath, /-attempt-1\.metadata\.json$/);
    }
    assert.notEqual(evidencePaths[0], evidencePaths[1]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("passMod DOM 指纹识别为百度安全验证", () => {
  assert.equal(
    detectWaf({ html: '<div class="passMod_puzzle-wrapper"></div>', title: "", text: "" }),
    "Baidu Security",
  );
});

test("作者页有足量正文时不因残留验证文案误判", () => {
  assert.equal(
    detectWaf({
      title: "艾儿天空",
      text: `${"作品列表与更新说明".repeat(30)}\n百度安全验证 拖动左侧滑块`,
      html: '<div class="passMod_puzzle-wrapper"></div><main>作品</main>',
    }),
    null,
  );
});

test("百度导航页残留验证文案不得被当作成功", () => {
  assert.equal(
    detectWaf({
      title: "艾儿天空",
      text: "百度首页 登录 艾儿天空 内容 6.1万 获赞 24 关注 1.2万 粉丝 百度安全验证",
      html: '<div class="passMod_puzzle-wrapper"></div>',
    }),
    "Baidu Security",
  );
});

test("真实页面的 octocaptcha 配置不触发通用验证码判定", () => {
  assert.equal(
    detectWaf({
      title: "GitHub - microsoft/generative-ai-for-beginners",
      text: "21 Lessons, Get Started Building with Generative AI ".repeat(4),
      html: '<script>window.__octocaptcha = { enabled: true };</script>',
    }),
    null,
  );
});

test("空壳页 + 大 HTML 不得渲染为成功正文", () => {
  const pageData = {
    url: "https://author.baidu.com/home/test",
    title: "",
    text: "",
    html: `<html>${"x".repeat(1200)}</html>`,
  };
  assert.equal(isHollowChallengePage(pageData), true);
  assert.throws(() => renderPage(pageData, "markdown"), /too thin|Baidu Security/);
});

test("仅有 passMod 无中文文案时也不得假成功", () => {
  assert.throws(
    () => renderPage({
      url: "https://author.baidu.com/home/test",
      title: "",
      text: "",
      html: `<html><div class="passMod_puzzle-wrapper"></div>${"x".repeat(1200)}</html>`,
    }, "markdown"),
    /Baidu Security/,
  );
});

test("人工挑战 stdin 检查使用 readable 而非 isReadable", () => {
  assert.equal(canUseHumanChallengeInput({ isTTY: true, readable: true }), true);
  assert.equal(canUseHumanChallengeInput({ isTTY: true, isReadable: true }), false);
  assert.equal(canUseHumanChallengeInput({ isTTY: false, readable: true }), false);
});

test("stealth 后 suggestion 指向人工验证启动器", () => {
  const hint = inferSuggestion({
    error: "Baidu Security blocked",
    html: "passMod_puzzle-wrapper",
    stealth: true,
  });
  assert.match(hint, /bash bin\/wfp-human\.sh/);
  assert.doesNotMatch(hint, /human-challenge|--save-state|--state/);
  assert.match(hint, /do not pipe|interactive TTY/i);
});

test("仅 passMod 空壳页 CLI 不得假成功", async () => {
  const root = await createCliFixture();
  try {
    await assert.rejects(
      () => runCli(root, ["--retries", "1"], { WFP_TEST_HOLLOW_PASSMOD: "1" }),
      (error) => {
        assert.equal(error.code, 1);
        assert.match(error.stderr, /Baidu Security|All attempts failed/);
        return true;
      },
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("renderPage 百度异常写入风控失败与人工验证提示", async () => {
  const root = await createCliFixture();
  const outputDir = join(root, "render-error-out");
  try {
    const error = await runCli(root, ["--stealth", "--output-dir", outputDir], { WFP_TEST_RENDER_BAIDU: "1" })
      .then(() => assert.fail("renderPage 百度异常必须失败"))
      .catch((caught) => caught);
    assert.equal(error.code, 1);
    assert.match(error.stderr, /No matching saved session was available/);
    const failurePath = error.stderr.match(/Evidence: (.+)$/m)?.[1];
    assert.ok(failurePath);
    const summary = JSON.parse(await readFile(failurePath, "utf8"));
    assert.equal(summary.failures[0].wafVendor, "Baidu Security");
    assert.match(summary.failures[0].suggestion, /bash bin\/wfp-human\.sh/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("renderPage 百度异常在人工模式进入验证流程", async () => {
  const root = await createCliFixture();
  const outputDir = join(root, "render-human-out");
  try {
    const error = await runCli(root, ["--stealth", "--output-dir", outputDir], {
      WFP_HUMAN_CHALLENGE: "1",
      WFP_TEST_RENDER_BAIDU: "1",
    })
      .then(() => assert.fail("renderPage 百度异常必须进入人工流程并失败"))
      .catch((caught) => caught);
    assert.equal(error.code, 1);
    const failurePath = error.stderr.match(/Evidence: (.+)$/m)?.[1];
    assert.ok(failurePath);
    const summary = JSON.parse(await readFile(failurePath, "utf8"));
    assert.equal(summary.failures[0].wafVendor, "Baidu Security");
    assert.equal(summary.failures[0].human.status, "non-tty");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("风控且无可用会话时失败提示只提供启动器命令", async () => {
  const root = await createCliFixture();
  const targetUrl = "https://blocked-sessionless.example.test/home/test?id=42";
  try {
    await assert.rejects(
      () => execFile(
        process.execPath,
        [RUNTIME_SCRIPT, targetUrl, "--retries", "1", "--stealth"],
        { env: cliEnv(root, { WFP_TEST_BAIDU_ALWAYS: "1" }) },
      ),
      (error) => {
        assert.equal(error.code, 1);
        assert.match(
          error.stderr,
          /bash bin\/wfp-human\.sh 'https:\/\/blocked-sessionless\.example\.test\/home\/test\?id=42'/,
        );
        assert.doesNotMatch(error.stderr, /--human-challenge|--save-state/);
        assert.match(error.stderr, /No matching saved session was available/);
        return true;
      },
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("公开 CLI 拒绝人工验证参数", async () => {
  const root = await createCliFixture();
  try {
    for (const option of ["--human-challenge", "--human-timeout"]) {
      await assert.rejects(
        () => runCli(root, [option]),
        (error) => {
          assert.equal(error.code, 1);
          assert.match(error.stderr, new RegExp(`Unknown option: ${option}`));
          return true;
        },
      );
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("成功抓取可 --save-state 落盘会话", async () => {
  const root = await createCliFixture();
  const statePath = join(root, "states", "site.json");
  try {
    const { stdout, stderr } = await runCli(root, ["--save-state", statePath]);
    assert.match(stdout.trim(), /\.md$/);
    assert.match(stderr, /Saved session state/);
    const state = JSON.parse(await readFile(statePath, "utf8"));
    assert.equal(state.cookies[0].name, "wfp");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("--state 会加载已有会话文件", async () => {
  const root = await createCliFixture();
  const statePath = join(root, "states", "site.json");
  await mkdir(dirname(statePath), { recursive: true });
  await writeFile(statePath, JSON.stringify({ cookies: [], origins: [] }), "utf8");
  try {
    const { stdout, stderr } = await runCli(root, ["--state", statePath], { WFP_TEST_REQUIRE_STATE: "1" });
    assert.match(stdout.trim(), /\.md$/);
    assert.match(stderr, /Loading session state/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("--state 文件不存在时直接失败", async () => {
  const root = await createCliFixture();
  try {
    await assert.rejects(
      () => runCli(root, ["--state", join(root, "missing-state.json")]),
      (error) => {
        assert.equal(error.code, 1);
        assert.match(error.stderr, /--state file not found/);
        return true;
      },
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
