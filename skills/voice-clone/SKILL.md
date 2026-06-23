---
name: voice-clone
description: 使用 Confucius4-TTS Gradio API 做参考音色克隆和文本转语音。
version: 1.0.0
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# Voice Clone

## 用途

用 Confucius4-TTS 在线 Demo API，把文本合成为参考音色语音。

默认参考音色：

```text
assets/miss-arrogant.mp3
```

## 快速使用

在本 Skill 目录执行：

```bash
python3 scripts/confucius4_tts.py --text "你好，这是一次声音克隆测试。" --out output.wav
```

使用文本文件：

```bash
python3 scripts/confucius4_tts.py --text-file input.txt --out output.wav
```

指定参考音色：

```bash
python3 scripts/confucius4_tts.py \
  --reference /path/to/reference.mp3 \
  --text-file input.txt \
  --out output.wav
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--text <text>` | 空 | 要合成的文本 |
| `--text-file <path>` | 空 | 从文件读取要合成的文本 |
| `--reference <path>` | `assets/miss-arrogant.mp3` | 参考音色 |
| `--lang <code>` | `zh` | 语言代码 |
| `--out <path>` | `voice-clone-output.wav` | 输出音频 |
| `--base-url <url>` | Confucius4-TTS Demo | Gradio 服务地址 |

`--text` 和 `--text-file` 必须提供一个；同时提供时优先使用 `--text`。

## Agent 工作流

当用户要合成语音时：

1. 确认参考音频和文本来源
2. 如用户直接给长文本，写入临时文本文件
3. 运行 `python3 scripts/confucius4_tts.py`
4. 确认输出 wav 文件存在和大小
5. 把输出路径反馈给用户

## 注意

- 该脚本只依赖 Python 标准库，调用公开 Gradio Demo，不需要 API Key
- 远端可能排队、限流或临时不可用
