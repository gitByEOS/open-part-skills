---
name: fetch-what-say
description: 抓取 yt-dlp 支持的网站媒体或本地视频，使用 mlx-whisper 生成 transcript.srt 和 transcript.txt，再基于文字稿生成 summary.txt 树形思维导图摘要。
version: 1.0.0
dependencies:
  - yt-dlp
  - ffmpeg
  - mlx-whisper
repository: https://github.com/gitByEOS/open-part-skills
---

# Fetch What Say

抓取媒体，看/听内容，说出总结，并生成可读网页。

核心流程：

```text
URL / 本地视频 -> yt-dlp / 本地复制 -> transcript.srt -> transcript.txt -> summary.txt -> viewer.html
```

## 快速使用

```bash
bash scripts/fetch-what-say.sh "https://www.bilibili.com/video/BV13jER6dEQT"
bash scripts/fetch-what-say.sh ~/Movies/local.mp4
bash scripts/fetch-what-say.sh --view ~/Downloads/fetch-what-say/<id>/
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

`summary.txt` 由 Agent 根据 `transcript.txt` 和下方固定提示词生成；脚本负责媒体抓取、转写和网页查看器。

## Cookies

优先使用显式 `--cookies`

不传 `--cookies` 时，脚本按 URL 域名匹配默认目录里的 `.txt`：

```text
~/Downloads/fetch-what-say/cookies/
```

例如 `bilibili_cookies.txt` 只会自动用于 `bilibili.com`

脚本不会读取浏览器 cookies，也不会读取环境变量

需要登录权限的网站：

1. 安装浏览器插件 `Get cookies.txt LOCALLY`
2. 打开目标网站并登录
3. 用插件导出 Netscape `cookies.txt`
4. 放入 `~/Downloads/fetch-what-say/cookies/`
5. 文件名必须包含域名关键词，如 `bilibili_cookies.txt`、`youtube_cookies.txt`

也可以显式传入：

```bash
bash scripts/fetch-what-say.sh "https://example.com/member/video" \
  --cookies ~/Downloads/site_cookies.txt
```

## 参数

常用参数：

| 参数 | 说明 |
|---|---|
| `input` | 完整 URL，或本地视频文件 |
| `--out <dir>` | 输出根目录，默认 `~/Downloads/fetch-what-say` |
| `--view <dir>` | 生成并打开 `viewer.html` |
| `--no-transcribe` | 只下载媒体，不转写 |

高级参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--height` | `360` | 最高分辨率 |
| `--prefer` | `size` | 同分辨率下偏小体积，或用 `bitrate` 偏高码率 |
| `--merge-format` | `mp4` | 合并容器格式 |
| `--model` | `mlx-community/whisper-large-v3-turbo` | `mlx-whisper` 模型 |
| `--language` | `zh` | 转写语言 |

## 查看结果

转写结果生成为纯文本，使用查看器获得更好阅读体验：

```bash
bash scripts/fetch-what-say.sh --view ~/Downloads/fetch-what-say/<id>/
```

- 自动生成 HTML 到工作目录并打开浏览器
- 提供「摘要/全文」标签页切换

## 总结流程

当用户要总结时：

1. 确认 `transcript.txt` 存在
2. 使用下方固定提示词总结全文
3. 写入同目录 `summary.txt`
4. 运行 `bash scripts/fetch-what-say.sh --view <work_dir>` 生成并打开网页

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
