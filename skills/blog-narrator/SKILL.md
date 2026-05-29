---
name: blog-narrator
description: 把博客 Markdown 导出为逐行披露演示 HTML，支持轻量预览和 Edge TTS 分段配音合并。当用户需要把博客转成演讲演示或配音 HTML 时使用
version: 1.0.2
dependencies:
  - python3
  - ffmpeg
  - edge-tts
repository: https://github.com/gitByEOS/open-part-skills
---

# Blog Narrator

## 用途

把博客 Markdown 导出成适合演讲的逐行披露 HTML

- 右方向键逐行出现，左方向键退回
- 初始只显示标题并居中；进入新 `## 标题` 时清空上一节，只保留标题与当前节
- 超长内容自动滚到底部
- 带预录音版：`Shift` 静音、`Ctrl` 重读当前行

## 模式选择

如果用户没有明确说明要“预览”还是“TTS”，必须使用 Ask 工具询问后再生成。

## 轻量预览（无预录音）

```bash
python3 {skill}/scripts/export_small_size.py input.md output.html [--open]
```

体积小，不含音频，用于验证排版；依赖浏览器朗读或现场讲解。

## TTS 分段工作流

在博客仓库根目录执行：

```bash
# 1. 分段
python3 {skill}/scripts/narrator_voice.py split input.md work_dir

# 2a. 自动配音（需 pip install edge-tts）→ audio/1.mp3, 2.mp3, …
python3 {skill}/scripts/narrator_voice.py gen work_dir [--voice xiaoxiao|xiaoyi] [--rate 1.175]

# 2b. 或手动：srt.md 各段复制到网页 TTS，音频下载到 work_dir/audio/
# 2c. 或者替换掉某些音频，比如流程图或者代码片段，再合成

# 3. 仅当 audio/ 内不是 N.mp3 命名时（备选）
python3 {skill}/scripts/narrator_voice.py match work_dir

# 4. 合并
python3 {skill}/scripts/narrator_voice.py merge work_dir [--open]
```

`gen` 已按段号命名时，跳过步骤 3，直接 `merge`。语速只在 `gen --rate` 设定。

工作目录：

```text
work_dir/ 
  src.md
  srt.md
  audio/       # 1.mp3, 2.mp3, …
  *_voice.html
```

## 依赖

| 脚本                                                     | 依赖                                               |
| ------------------------------------------------------ | ------------------------------------------------ |
| `export_small_size` / `narrator_voice split` / `merge` | Python 3 标准库                                     |
| `narrator_voice gen`                                   | `edge-tts`                                       |
| `narrator_voice match`（备选）                           | `onnxruntime`, `numpy`；模型首次下载到 `scripts/models/` |

图片：`(/pics/...)` 相对 cwd；可用 `BLOG_NARRATOR_IMAGE_BASE` 覆盖。

## 修改规则

- 核心库（MD→HTML、stage、ASR）：`scripts/narrator_core.py`
- 分段配音 CLI：`scripts/narrator_voice.py`（`split` / `gen` / `match` / `merge`）

