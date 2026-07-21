---
name: md-to-png
description: 把 Markdown 文件渲染成手机友好的 HTML，再调用 html-cut 截图为高清 PNG。用户提到 md-to-png、md 转 png、md 截图、把 md 发到手机看时使用。
version: 1.0.0
dependencies:
  - python3
  - html-cut
  - playwright
repository: https://github.com/gitByEOS/open-part-skills
---

# Markdown → PNG

把任意 `.md` 渲染成 VitePress 风格的自包含 HTML，再借助 `html-cut` 截图为高清 PNG，方便手机查看或通过聊天工具发送。

## 启动

```bash
python3 scripts/md_to_png.py path/to/skill.md /tmp/out.png
```

成功时 stdout 仅输出 PNG 绝对路径（与 `html-cut` 输出约定一致）。

## 参数

| 参数 | 说明 |
|---|---|
| `md` | Markdown 文件路径 |
| `output` | PNG 输出路径，可省略，默认写入系统临时目录 |
| `--title` | HTML 标题，默认取 md 首个 `#` 标题 |
| `--width` | 视口宽度，默认 `740`（手机阅读友好） |
| `--height` | 视口高度，默认 `900` |
| `--scale` | 设备像素比，默认 `2` |
| `--color-scheme` | `light` 或 `dark`，默认 `light` |
| `--wait MS` | 加载后额外等待毫秒，默认 `500` |

## 常见示例

```bash
# 默认亮色、740 宽，适合手机阅读
python3 scripts/md_to_png.py SKILL.md /tmp/skill.png

# 宽屏深色
python3 scripts/md_to_png.py README.md /tmp/readme.png \
  --width 1280 --scale 3 --color-scheme dark
```

## 工作流

1. 确认输入 md 文件存在
2. 脚本自动定位同仓库的 `skills/html-cut/scripts/capture.py` 做截图
3. 执行后检查 stdout 的 PNG 绝对路径，必要时通过 lan-chat 等工具代发给用户

## 渲染范围

极简 Markdown 转换，覆盖：YAML frontmatter（自动去除）、标题 `#`、段落、无序列表 `-`、 fenced 代码块、GFM 表格、行内 `code` / `**bold**` / `[link](url)`。不渲染图片、引用块、有序列表等高级语法。

## 依赖

- **html-cut**：截图由 `html-cut` skill 的 `capture.py` 完成，需先安装 Playwright 与 Chromium
- 未安装时会以非零退出码报错，按 `html-cut` SKILL.md 的故障排查处理

## 注意事项

本 skill 截图依赖同仓库的 `html-cut` skill

| 现象 | 处理 |
|---|---|
| `找不到 html-cut 脚本` | `npx skills add https://github.com/gitByEOS/open-part-skills --skill html-cut` |
| `Chromium 找不到` / `Executable doesn't exist` | `python3 -m playwright install chromium` |

## Agent 注意

- 用户未给输出路径时，输出到临时目录，避免覆盖项目已有文件
- 截图完成后反馈绝对 PNG 路径；不要把二进制图片内容粘进回复
- 若需把截图发给用户，可结合 `lan-chat` 的代发文件能力
