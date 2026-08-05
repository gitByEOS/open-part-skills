---
name: webfetch-plus
description: 使用 Browser 抓取普通 WebFetch 失败的网页；支持 --stealth、通过 `bin/wfp-human.sh` 人工处理反爬。当用户明确提到 webfetch-plus、或 WebFetch 失败、或页面有验证码/WAF 时使用
version: 1.2.0
dependencies:
  - node (>=20)
npm_dependencies:
  - cloakbrowser
  - playwright-core
repository: https://github.com/gitByEOS/open-part-skills
---

# WebFetch Plus

## 执行原则

- 把当前 skill 路径设置给 `WFP_PATH`
- 任何命令执行，必须先 `cd "$WFP_PATH"`
- 普通抓取可用管道，跳过安全提示
- 管道输入按空白字符拆分参数；URL 和参数值不得包含空格
- 脚本按 `runtime/node/package.json` 自动安装 CloakBrowser 与 Playwright；首次安装会使用进程锁，其他调用会等待完成
- **Agent / 非 TTY 环境不要运行人工验证流程**；脚本会从 `/tmp/wfp-states/*.json` 自动选择匹配目标域名的最新会话，找不到时才报告需要交互验证
- 默认 state 路径的唯一权威是 runtime 的 `getDefaultStatePath()`：`/tmp/wfp-states/<hostname-clean>.json`（`hostname-clean` 为 URL hostname 中非字母数字和连字符替换为 `-` 的结果）。不要在调用方自行猜测或另行实现该命名。

## 外部副作用

- 访问传入的 HTTP(S) URL，并启动本地浏览器；`--stealth` 首次使用可能下载 Chromium
- 正文默认写入 `/tmp/wfp-tasks/`
- 失败证据始终写入 `/tmp/wfp-evidence/`，不受 `--output-dir` 影响
- `--save-state` 会写入 Playwright `storageState` JSON（cookies / localStorage）；文件可能含登录态，勿提交到 git
- `--out` 和 `--output-dir` 会写入调用方指定路径；不要让多个调用共用同一 `--out` 路径

## 抓取网页

管道传入 URL 和参数：

```bash
echo "https://example.com" | bash "bin/wfp.sh"
```

也可直接传参：

```bash
bash bin/wfp.sh "https://example.com" --wait 3000
```

脚本在 stdout 输出正文文件路径。

### 动态页面超时

动态页面长期保持连接时，`networkidle` 可能连续导航超时。此时改用 `--wait-until domcontentloaded`，并按页面实际加载时间提高 `--timeout`；例如：

```bash
bash bin/wfp.sh 'https://example.com' --wait-until domcontentloaded --timeout 90000
```

## 验证码、登录与会话复用

遇到人机验证或登录时，在交互 TTY 中运行启动器，完成验证后按回车。启动器会以 headed + stealth 模式保存该目标的默认会话；未显式传入 `--wait-until` 时使用 `domcontentloaded`，显式值优先：

```bash
bash bin/wfp-human.sh 'https://example.com/protected-page'
```

后续普通抓取会复用会话：`--state` 优先；未提供时，脚本从 `/tmp/wfp-states/*.json` 中验证 cookie 域名或 localStorage origin 与目标域名匹配，并采用最新文件。会话过期再次被拦时，重新运行启动器即可覆盖默认 state。

风控拦截且没有可复用会话时，stderr 会输出一条带实际目标 URL 的可复制启动器命令。自动任务和 Agent 不运行启动器，只使用已有或自动发现的会话。非 TTY 的 macOS 调用会自动打开 Terminal。

## 参数

| 参数 | 说明 |
|------|------|
| `--out <path>` | 直接写入指定文件；同一路径不可并发使用 |
| `--output-dir <path>` | 将唯一正文文件直接写入该目录 |
| `--visible` | 显式打开浏览器窗口（headed）；默认隐式 headless |
| `--state <path>` | 显式加载 Playwright storageState JSON（优先于自动发现；文件必须已存在） |
| `--save-state <path>` | 抓取成功后保存 storageState JSON |
| `--wait <ms>` | 页面加载后额外等待时间 |
| `--timeout <ms>` | 页面导航超时时间，默认 45000 |
| `--wait-until <load|domcontentloaded|networkidle>` | 页面加载完成条件，默认 `networkidle` |
| `--retries <1-3>` | 最多尝试次数，默认 3；首次发现 WAF 时后续自动 `--stealth` |
| `--selector <css>` | 只抽取指定 CSS 选择器内容 |
| `--format <markdown|text|html>` | 输出格式，默认 `markdown`；需要链接时用 `html` |
| `--stealth` | CloakBrowser 定制 Chromium 增强反 WAF |

人工验证不属于公开 `wfp.sh` 参数。仅通过 `bash bin/wfp-human.sh '<url>' [fetch options]` 启动；启动器会强制 headed 与 stealth，并保存默认 state。它拒绝 `--state`、`--save-state`、`--out`、`--visible` 等受管理参数。

## 执行流程

```text
传入 URL →（优先 --state，否则自动匹配本地会话）→ 抓取
  → 若 WAF：自动 stealth 重试 → 仍失败则提示 wfp-human.sh 启动器
  → 启动器内部启用人工验证 → 等人回车 → reload 目标 URL → 保存 state
  → 成功则可选 --save-state → stdout 输出正文路径
```

**成功判定**：stdout 输出唯一正文路径
- 空标题 + 极短正文 + 大 HTML / 可见挑战文案 → 失败
- 已有真实标题且正文够长时，不因 HTML 中残留挑战相关 CSS 或文案误判失败

**失败处理契约**：
1. 非零退出；stderr 输出 failure summary 路径，evidence 的 `suggestion` 保留同一建议
2. 首次 WAF → 剩余重试自动 `--stealth`
3. stealth 仍失败且没有匹配的 `/tmp/wfp-states/*.json` 会话 → 最终 stderr 只输出一条带实际目标 URL 的完整可复制启动器命令：`bash bin/wfp-human.sh '<url>'`
4. 人工挑战同页可多次回车；挑战未消失会提示再试，不会立刻关页重开三轮

**通用规则**：
- 默认 headless；启动器内部人工挑战强制 headed，且不隐藏启动窗口
- 启动器不自动解滑块
- 无人值守任务只用 `--state`，不要运行启动器
