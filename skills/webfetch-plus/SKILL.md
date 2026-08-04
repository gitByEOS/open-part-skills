---
name: webfetch-plus
description: 使用 Browser 抓取普通 WebFetch 失败的网页内容，并输出适合大模型阅读的正文文本。当用户明确提到 webfetch-plus 或使用 webfetch 失败时使用
version: 1.1.0
dependencies:
  - node
npm_dependencies:
  - cloakbrowser@0.5.3
  - playwright-core@1.60.0
repository: https://github.com/gitByEOS/open-part-skills
---

# WebFetch Plus

## 执行原则

- 把当前 skill 路径设置给 `WFP_PATH`
- 任何命令执行，必须先 `cd "$WFP_PATH"`
- 使用管道形式，跳过安全提示
- 管道输入按空白字符拆分参数；URL 和参数值不得包含空格
- 脚本按 `runtime/node/package.json` 自动安装 CloakBrowser 与 Playwright；首次安装会使用进程锁，其他调用会等待完成

## 外部副作用

- 访问传入的 HTTP(S) URL，并启动本地浏览器；`--stealth` 首次使用可能下载 Chromium
- 正文默认写入 `/tmp/wfp-tasks/`，失败证据默认写入 `/tmp/wfp-evidence/`
- `--out` 和 `--output-dir` 会写入调用方指定路径；不要让多个调用共用同一 `--out` 路径

## 抓取网页

管道传入 URL 和参数：

```bash
echo "https://example.com" | bash "bin/wfp.sh"
```

需要参数时追加：

```bash
echo "https://example.com --wait 3000" | bash "bin/wfp.sh"
```

脚本在 stdout 输出正文文件路径。默认正文直接写入临时任务目录：

```text
/tmp/wfp-tasks/yyMMdd-HH-mm-<url-label>-<8hex>.md
```

## 多个 URL

多个 URL 可并发打开。每次调用会生成唯一的正文文件：

```bash
echo "https://a.com" | bash bin/wfp.sh
echo "https://b.com" | bash bin/wfp.sh
```

`--output-dir` 将唯一正文文件直接写入指定目录，可并发调用：

```bash
echo "https://a.com --output-dir /tmp/wfp" | bash bin/wfp.sh
echo "https://b.com --output-dir /tmp/wfp" | bash bin/wfp.sh
```

## 参数

| 参数 | 说明 |
|------|------|
| `--out <path>` | 直接写入指定文件；同一路径不可并发使用 |
| `--output-dir <path>` | 将唯一正文文件直接写入该目录 |
| `--visible` | 显式打开浏览器窗口；默认隐式 headless |
| `--wait <ms>` | 页面加载后额外等待时间 |
| `--timeout <ms>` | 页面导航超时时间，默认 45000 |
| `--wait-until <load|domcontentloaded|networkidle>` | 页面加载完成条件，默认 `networkidle` |
| `--retries <1-3>` | 最多尝试次数，默认 3；首次发现 WAF/验证码时，后续尝试自动切换 `--stealth` |
| `--selector <css>` | 只抽取指定 CSS 选择器内容 |
| `--format <markdown|text|html>` | 输出格式，默认 `markdown` |
| `--stealth` | 使用 CloakBrowser 定制的 Chromium 增强反 WAF 能力 |

## 执行流程

```text
管道传入 URL → 执行脚本 → stdout 输出路径 → 读取正文
```

**成功判定**：stdout 输出唯一正文路径即成功，直接读取

**失败处理**：
1. 命令以非零状态退出，stderr 输出 `/tmp/wfp-evidence/<stem>-failure-summary.json` 或指定输出目录下证据路径
2. 读取该目录中 `<stem>-attempt-N.metadata.json` 的 `suggestion` 字段
3. 首次识别 WAF 或验证码时，剩余重试自动使用 `--stealth`
4. 若仍失败，读取建议后按需增加参数重新执行，如 `--wait 3000`
5. Playwright 仅提供浏览器自动化与拖拽 API，不处理解答、滑块等反自动化机制，工具不会执行，只会保留证据并要求用户完成授权交互

**通用规则**：
- 默认 headless，不加 `--visible`
- 默认和同一 `--output-dir` 中的并发调用会生成唯一正文文件
- 默认与 `--out` 的失败证据写入 `/tmp/wfp-evidence/`；`--output-dir` 的失败证据写入其下的 `webfetch-plus-evidence/`
- `--out` 同一路径不可并发使用
