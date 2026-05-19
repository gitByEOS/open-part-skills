---
name: webfetch-plus
version: 1.0.2
description: 使用 Browser 抓取普通 WebFetch 失败的网页内容，并输出适合大模型阅读的正文文本。当用户明确提到 webfetch-plus 或使用 webfetch 失败时使用
license: MIT
repository: https://github.com/gitByEOS/open-part-skills
dependencies:
  - cloakbrowser@0.3.28
  - playwright-core@1.60.0
---

# WebFetch Plus

## 首次准备

前置条件：把当前 skill 路径设置给 `WFP_PATH`。

```bash
WFP_PATH={skill}
```

首次使用前安装依赖：

```bash
cd "$WFP_PATH" && npm ci --prefix runtime/node
```

## 抓取网页

写入 URL 到输入文件，再执行固定命令：

```bash
echo "https://example.com" > "$WFP_PATH/runtime/.wfp_input"
bash "$WFP_PATH/bin/wfp.sh"
```

需要参数时追加到文件：

```bash
echo "https://example.com" > "$WFP_PATH/runtime/.wfp_input"
echo "--wait" >> "$WFP_PATH/runtime/.wfp_input"
echo "3000" >> "$WFP_PATH/runtime/.wfp_input"
bash "$WFP_PATH/bin/wfp.sh"
```

后台运行不阻塞，末尾加 `&`：

```bash
echo "https://example.com" > "$WFP_PATH/runtime/.wfp_input"
bash "$WFP_PATH/bin/wfp.sh" &
```

脚本默认写入运行目录，stdout 只打印结果文件路径：

```text
runtime/runs/new/page_1.md
```

## 多个 URL

依次覆盖写入，后台执行：

```bash
echo "https://a.com" > "$WFP_PATH/runtime/.wfp_input"
bash "$WFP_PATH/bin/wfp.sh" &
echo "https://b.com" > "$WFP_PATH/runtime/.wfp_input"
bash "$WFP_PATH/bin/wfp.sh" &
```

注意：多个 URL 快速写入同一文件会有竞争，需要指定不同 `--task` 并错开写入时间。

## 参数

| 参数 | 说明 |
|------|------|
| `--out <path>` | 写入指定文件 |
| `--output-dir <path>` | 写入自定义目录 |
| `--archive` | 保留本次运行到 `runtime/runs`，默认不开 |
| `--visible` | 显式打开浏览器窗口；默认隐式 headless |
| `--wait <ms>` | 页面加载后额外等待时间 |
| `--timeout <ms>` | 页面导航超时时间，默认 45000 |
| `--wait-until <load|domcontentloaded|networkidle>` | 页面加载完成条件，默认 `networkidle` |
| `--retries <1-3>` | 最多尝试次数，默认 3 |
| `--selector <css>` | 只抽取指定 CSS 选择器内容 |
| `--format <markdown|text|html>` | 输出格式，默认 `markdown` |
| `--task <n>` | 任务标识，隔离输出文件为 `page_{n}.md` 等，默认 1。多个任务可并行写入 `runtime/runs/new/` 互不覆盖 |
| `--stealth` | 使用 CloakBrowser 定制的 Chromium 增强反 WAF 能力 |

## 执行规则

1. 先运行脚本抓取页面
2. 读取 stdout 给出的结果文件
3. 如果失败，读取 `failure_summary_{n}.json` 和 `attempt_{n}_{N}.metadata.json`。
4. 每次失败都会保存 `attempt_{n}_{N}.html` 和 `attempt_{n}_{N}.metadata.json`，不保存截图
5. 下一次只根据 metadata 的 `suggestion` 增加一个参数
6. 默认隐式启动浏览器，不要加 `--visible`，除非需要人工观察页面
7. 多个 URL 需要同时抓取时，用不同 `--task` 值并行，避免输出互相覆盖
