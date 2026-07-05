---
name: fetch-what-say
description: 抓取 yt-dlp 支持的媒体或本地视频，转写成文字稿，Agent 生成树形思维导图摘要，输出可读网页。
version: 1.1.0
dependencies:
  - yt-dlp
  - ffmpeg
  - mlx-whisper
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# Fetch What Say

```text
URL / 本地视频 -> yt-dlp / 复制 -> transcript.srt -> transcript.txt -> summary.txt -> viewer.html
```

## 依赖

Python 包：

```bash
pip install esflow>=0.1.2 mlx-whisper
```

系统二进制（yt-dlp / ffmpeg）：

```bash
brew install yt-dlp ffmpeg          # macOS
sudo apt install yt-dlp ffmpeg      # Debian/Ubuntu
```

## 快速使用

```bash
python3 scripts/run.py "https://www.bilibili.com/video/BV1pzjy6GEkC"
python3 scripts/run.py ~/Movies/local.mp4
python3 scripts/run.py --view ~/Downloads/fetch-what-say/<id>/
```

输出目录：

```text
<out>/<id>/
├── video.<ext>
├── transcript.srt
├── transcript.txt
├── summary.txt
└── viewer.html
```

`summary.txt` 由 Agent 用下方 `Summary Prompt` 生成，脚本负责抓取、转写、网页查看器。

## Flow 结构

esflow DAG 编排（`scripts/flow.py` 声明，`scripts/nodes/` 各节点）：

```text
resolve → download → extract_audio → transcribe → agent_summary → export_html
```

- `resolve`：解析 input/cookies，算 media_id，建 work_dir，产出 plan
- `download`：URL 走 yt-dlp，本地文件复制到 work_dir
- `extract_audio`：ffmpeg 提取 16k 单声道 wav
- `transcribe`：mlx-whisper 转写，产出 transcript.srt 与 transcript.txt
- `agent_summary`：TO_AGENT 节点，跑到达它时退出进程（exit 2），Agent 写 summary.txt 后续跑
- `export_html`：生成 viewer.html 并弹出

## Agent 介入

```bash
# 1. 首跑：到达 agent_summary 节点,进程退出码 2
python3 scripts/run.py "https://www.bilibili.com/video/BVxxx"
# stderr 打印 [to_agent] 完成后续跑:python3 scripts/run.py --resume <job_dir>

# 2. Agent 读上游产物里的 transcript.txt,用下方 Summary Prompt 写 summary.txt 到 work_dir

# 3. 续跑生成 viewer.html
python3 scripts/run.py --resume <job_dir>
```

调试单节点：`esflow run scripts/ --node transcribe`（上游从产物目录复用）。

## Cookies

优先使用显式 `--cookies`；不传时按 URL 域名匹配 `~/Downloads/fetch-what-say/cookies/` 下的 `.txt`。例如 `bilibili_cookies.txt` 只会自动用于 `bilibili.com`。脚本不读浏览器 cookies，也不读环境变量。

需要登录权限的网站：用浏览器插件 `Get cookies.txt LOCALLY` 导出 Netscape `cookies.txt`，放入上述目录，文件名须包含域名关键词。

## 参数

常用：

| 参数 | 说明 |
|---|---|
| `input` | 完整 URL，或本地视频文件 |
| `--out <dir>` | 输出根目录，默认 `~/Downloads/fetch-what-say` |
| `--view <dir>` | 生成并打开 `viewer.html`（不进 flow） |
| `--no-transcribe` | 只下载媒体，不转写 |
| `--resume <job_dir>` | 续跑 TO_AGENT 节点 |
| `--dry-run` | 只跑 resolve 产出 plan |
| `--schema` | 输出 JSON 契约 |

高级：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--height` | `360` | 最高分辨率 |
| `--prefer` | `size` | 同分辨率下偏小体积，或 `bitrate` 偏高码率 |
| `--merge-format` | `mp4` | 合并容器格式 |
| `--model` | `mlx-community/whisper-large-v3-turbo` | `mlx-whisper` 模型 |
| `--language` | `zh` | 转写语言 |

退出码：`0 ok / 1 runtime / 2 to_agent / 3 validation / 4 auth`

## Summary Prompt

```text
请阅根据下方文章对话或教程内容，生成一份结构化的思维导图式摘要。

输出格式要求：
1. 根节点（第0层）：用文档的核心主题提炼出一个概括性标题，单独置于顶部，不加序号，不加树形前缀。标题下方用树形符号（│ 和 ├─）连接下一层。
2. 一级分支：用带圆圈的数字编号（①、②、③、④…）标记每个主要主题，置于同一列，上方共用一条水平主干线。
3. 二级及以下分支：使用 ASCII 树形符号（├─、└─、│）表示层级关系，缩进体现父子关系。
4. 展开深度：至少到三级（根 > ① > ├─ > └─），根据需要可到四级。
5. 节点内容：不得出现完整段落，每句话不超过25字，每句话必须增加信息密度，同类合并。
6. 内容组织：完全根据文档实际内容提炼主题，不预设任何固定板块。自动识别文章的论述结构（可按论点分层、问题分类、时间顺序、人物观点、结论建议等逻辑），动态生成分支。
7. 输出纯文本

风格要求：
- 拒绝散文式叙述，拒绝连接词和过渡句
- 每条只呈现关键事实、判断或结论
- 同一层级条目数量不限，但力求均衡

格式示例如下：

文档核心标题
│
├─ ① 第一主题
│   ├─ 子要点A
│   │   ├─ 细节1
│   │   └─ 细节2
│   └─ 子要点B
│       └─ 细节3
├─ ② 第二主题
│   ├─ 子要点C
│   │   └─ 细节4
│   └─ 子要点D
└─ ③ 第三主题
    ├─ 子要点E
    └─ 子要点F

请**严格按照上述格式**（根节点独立 + 树形符号 + 圆圈序号）生成，内容完全基于您对下方内容的理解。
```
