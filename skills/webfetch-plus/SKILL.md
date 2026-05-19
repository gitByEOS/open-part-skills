---
name: webfetch-plus
version: 1.0.3
description: 使用 Browser 抓取普通 WebFetch 失败的网页内容，并输出适合大模型阅读的正文文本。当用户明确提到 webfetch-plus 或使用 webfetch 失败时使用
license: MIT
repository: https://github.com/gitByEOS/open-part-skills
dependencies:
  - cloakbrowser@0.3.28
  - playwright-core@1.60.0
---

# WebFetch Plus

## 执行原则

- 把当前 skill 路径设置给 `WFP_PATH`。
- 任何命令执行，必须先 `cd "$WFP_PATH"` 

## 抓取网页

管道传入 URL 和参数：

```bash
echo "https://example.com" | bash "bin/wfp.sh"
```

需要参数时追加：

```bash
echo "https://example.com --wait 3000" | bash "bin/wfp.sh"
```

脚本输出结果文件路径：

```text
runtime/runs/new/page_1.md
```

## 多个 URL

同时打开多个，需要追加 `--task N`，不要用`&`后台执行：

```bash
echo "https://a.com --task 1" | bash bin/wfp.sh
echo "https://b.com --task 2" | bash bin/wfp.sh
```

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
| `--task <n>` | 任务标识，隔离输出文件为 `page_{n}.md` 等，默认 1 |
| `--stealth` | 使用 CloakBrowser 定制的 Chromium 增强反 WAF 能力 |

## 执行流程

```text
管道传入 URL → 执行脚本 → stdout 输出路径 → 读取结果
```

**成功判定**：stdout 输出 `page_{n}.md` 路径即成功，直接读取。

**失败处理**：
1. 读取 `attempt_{n}_{N}.metadata.json` 的 `suggestion` 字段
2. 根据建议增加一个参数重试（如 `--wait 3000`）
3. 最多 3 次重试

**通用规则**：
- 默认 headless，不加 `--visible`
- 多 URL 串行执行，用不同 `--task` 区分输出
