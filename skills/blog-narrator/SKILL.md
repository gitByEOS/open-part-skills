---
name: blog-narrator
description: 把博客 Markdown 导出为逐行披露演示 HTML，支持轻量预览和 Edge TTS 分段配音合并。当用户需要把博客转成演讲演示或配音 HTML 时使用
version: 1.1.0
dependencies:
  - python3
  - ffmpeg
  - edge-tts
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# Blog Narrator

```text
Markdown → parse_md → { 预览 HTML | split → gen → (match) → merge → 配音 HTML }
```

## 用途

把博客 Markdown 导出成适合演讲的逐行披露 HTML

- 右方向键逐行出现，左方向键退回
- 初始只显示标题并居中；进入新 `## 标题` 时清空上一节，只保留标题与当前节
- 带预录音版：`Shift` 静音、`Ctrl` 重读当前行

## 模式选择

如果用户没有明确说明要「预览」还是「TTS」，必须使用 Ask 工具询问后再生成。

## 依赖

Python 包：

```bash
pip install esflow edge-tts
```

系统二进制（解码音频）：

```bash
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian/Ubuntu
```

- 预览 / split / merge：Python 3 标准库
- `gen`：`edge-tts`
- `match`（备选对齐）：`onnxruntime`、`numpy`，模型首次下载到 `scripts/models/`

图片：`(/pics/...)` 相对 cwd；可用 `BLOG_NARRATOR_IMAGE_BASE` 覆盖。

## 快速使用

```bash
# 轻量预览(无预录音,体积小,验证排版)
python3 scripts/run.py preview input.md output.html [--rate 1.15] [--open]

# TTS 分段配音(一次跑完 split→gen→(match)→merge)
python3 scripts/run.py tts input.md work_dir [--voice xiaoxiao|xiaoyi] [--rate 1.175] [--open]
```

**默认行为**：预览写 `output.html`；TTS 写 `work_dir/{stem}_voice.html`，`--open` 自动打开浏览器。

## 产物形态

| 模式 | 音频来源 | 体积 | 适用 |
|---|---|---|---|
| 预览 HTML | 浏览器 SpeechSynthesis 朗读(无预录音)，含 voice 面板可点击播放 | 小 | 快速验证排版、现场讲解 fallback |
| TTS HTML | edge-tts 预录音 base64 内嵌，`work_dir/audio/N.mp3` 为分段源 | 大 | 离线演讲、音色稳定 |

两种产物都是自包含单文件，均带 voice 面板（`Shift` 静音、`Ctrl` 重读当前行）。差异只在音频来源：预览靠浏览器合成零依赖，TTS 内嵌预录音。

- **工作目录**(TTS 模式)：

```text
work_dir/
  src.md            # 原始 Markdown 副本
  srt.md            # 分段清单(## [N] 标记)
  audio/            # 1.mp3, 2.mp3, …
  {stem}_voice.html # 合成产物
  .esflow-jobs/     # esflow 运行状态(--from 续跑用)
```

## Flow 结构

esflow DAG 编排(`scripts/flow.py` 声明，`scripts/nodes/` 各节点)：

```text
parse_md ──→ export_preview         (mode=preview)
        └──→ split → gen → match → merge   (mode=tts)
```

单 flow 双路径，由子命令决定 `mode`，节点 `accept` 据此跳过：

| 节点 | 职责 |
|---|---|
| `parse_md` | strip frontmatter/分割线 → HTML + 抽标题/段文本 |
| `export_preview` | 仅 `mode=preview`，生成轻量 HTML |
| `split` | 仅 `mode=tts`，写 `work_dir/src.md` + `srt.md` + `audio/` |
| `gen` | Edge TTS 分段合成 `audio/N.mp3` |
| `match` | **条件**：`audio/` 有非 `N.mp3` 命名文件时 ASR 对齐重命名 |
| `merge` | 合成内嵌 base64 音频的 HTML |

`match` 跳过时 `merge` 照跑——`merge` 直读 `split.audio_dir`，不依赖 `match` 产物。无 TO_AGENT 断点，一次跑完。

调试单节点：在 skill 根目录 `esflow run scripts/ --node <节点 id>`（上游从 job 产物复用）。

## 续跑：替换音频后只跑 match+merge

标准 TTS 流程 `gen` 总是产出 `N.mp3`，`match` 自动跳过。若要**手动替换/补充音频**(如流程图、代码片段用自定义音色)：

```bash
# 1. 先正常跑一次,拿到 job 目录
python3 scripts/run.py tts input.md work_dir

# 2. 手动改 audio/:替换某些 N.mp3,或按 srt.md 段号放入网页 TTS 下载的音频(可非 N.mp3 命名)

# 3. 从 match 续跑(上游 split/gen 从 job 目录加载,不重跑)
python3 scripts/run.py tts input.md work_dir --from match --job-dir work_dir/.esflow-jobs/blog-narrator/<job时间戳>
```

`match` 用 ASR 识别非命名音频并重命名为 `N.mp3`，`merge` 重新合成 HTML。`--from` 也可指定 `merge` 只重合成。

## 参数

### preview 子命令

| 参数 | 说明 |
|---|---|
| `input` | 输入 Markdown |
| `output` | 输出 HTML 路径 |
| `--rate` | 默认语速，默认 1.15 |
| `--open` | 生成后打开浏览器 |

### tts 子命令

| 参数 | 说明 |
|---|---|
| `input` | 输入 Markdown |
| `work_dir` | 工作目录(存 src.md/srt.md/audio/产物) |
| `--voice` | 音色 `xiaoxiao`/`xiaoyi`，默认 `xiaoxiao` |
| `--rate` | 语速，默认 1.175 |
| `--open` | 生成后打开浏览器 |
| `--from NODE` | 从指定节点续跑该节点及下游，上游从 `--job-dir` 加载 |
| `--job-dir DIR` | `--from` 续跑时必填，指向上次 job 目录 |

## 异常处理

| 情况 | 行为 |
|------|------|
| 输入文件不存在 | 预检失败，退出码 3 |
| `--voice` 非法 | `bad_voice` 错误，退出码 3 |
| `--rate` 非数字 | `bad_rate` 错误，退出码 3 |
| edge-tts 合成失败 | 单段失败跳过，日志 `⚠️ 失败`，不中断整体 |
| `match` 缺 onnxruntime | `no_onnxruntime` 错误，退出码 1 |
| `--from` 未配 `--job-dir` | 退出码 3 |

## Agent 使用指引

用户提到「博客转演示」「逐行披露 HTML」「博客配音」时使用本 skill：

1. **先用 Ask 确认模式**：预览还是 TTS
2. 预览：`python3 scripts/run.py preview <input.md> <output.html> --open`
3. TTS：`python3 scripts/run.py tts <input.md> <work_dir> --open`
4. 若用户要替换某些音频：引导用 `--from match --job-dir <上次job>` 续跑
5. 确认产物 HTML 路径并反馈给用户

## 修改规则

- 核心库（MD→HTML、stage、ASR）：`scripts/narrator_core.py`
- DAG 声明：`scripts/flow.py`；节点实现：`scripts/nodes/`
- CLI 与 envelope：`scripts/run.py`、`scripts/common.py`
