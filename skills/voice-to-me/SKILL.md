---
name: voice-to-me
description: 将回复生成 MP3 语音并通过 QQ 发送。用户要求语音回复、音频回复、朗读、“语音回复”、“发语音”、“读给我听”，或希望答案以语音形式交付时使用
version: 1.0.0
dependencies:
  - python3
  - ffmpeg
  - "edge-tts>=7.0,<8"
repository: https://github.com/gitByEOS/open-part-skills
---

# 语音回复

将回答整理为简洁自然的口语稿，在当前会话工作区生成 MP3，并通过 QQ 返回

## 依赖

```bash
python3 -m pip install "edge-tts>=7.0,<8"
```

系统还须安装 `ffmpeg`，用于默认降噪和追加尾部静音

## 生成音频

1. 保持朗读文本自然，移除 Markdown 语法、不应朗读的 URL、文件标签和模型或会话元数据。
2. 输出必须位于当前工作目录，QQ 网关才能接收。默认路径为 `.qq-voice/reply-<timestamp>.mp3`
3. 从可用 Skills 列表中获取本 Skill 的目录路径，然后运行：

```bash
python3 "<skill-dir>/scripts/voice_to_me.py" \
  --text "要朗读的内容" \
  --output "$PWD/.qq-voice/reply-$(date +%Y%m%d-%H%M%S).mp3"
```

默认人设配置：`xiaoyi`（`zh-CN-XiaoyiNeural`）、`+7Hz` 音高和 `--rate 1.13`（`+13%` 语速）。仅当用户明确偏好更成熟的声音时，才使用 `--voice xiaoxiao`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--voice` | `xiaoyi` | 音色；用户明确偏好成熟音色时使用 `xiaoxiao` |
| `--rate` | `1.13` | 语速，范围 `0.5`–`2.0` |
| `--tail-silence` | `0.5` | 语音结尾静音秒数，范围 `0`–`5` |
| `--denoise` | 开启 | 轻度高通、去齿音、低通，抑制低频隆隆声与高频嘶声 |
| `--no-denoise` | 关闭降噪 | 仅在用户要求保留原始音色时使用 |

对于较长或含 Shell 特殊字符的文本，将朗读内容保存到会话工作区，再使用 `--text-file <path>` 代替 `--text`

默认开启轻度降噪，并通过 MP3 流复制追加尾部静音，避免为停顿而二次编码。降噪会额外消耗少量 CPU 并重新编码音频；它不一定能消除合成语音本身的高频纹理，因此需要保留原始音色时使用 `--no-denoise`

## 通过 QQ 返回

成功生成后，在最终回复中单独另起一行添加以下标签：

```text
<qqvoice>/absolute/path/to/reply.mp3</qqvoice>
```

- 使用脚本打印的绝对路径。不要将该标签置于 Markdown 代码块中
- 语音回复时不需要回复其他文字
