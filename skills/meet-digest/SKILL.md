---
name: meet-digest
description: >-
  把会议录音 wav 转写成带时间轴全文，再提炼成结构化会议总结：主题、讨论问题、分话题的痛点/原因/会上方案、待办与未决项。必须基于原文禁止编造。用户提到会议总结、会议纪要、srt.md、转写分析、meet-digest、落盘会议时使用。
version: 1.0.0
dependencies:
  - python3
  - esflow
  - faster-whisper
  - imageio-ffmpeg
repository: https://github.com/gitByEOS/open-part-skills
---

# 会议转写提炼

把一份会议录音压成可追溯的总结，不补会外方案。没有 wav 就停，去要路径。禁止手跑识别，只调 `scripts/run.py`。

## 依赖

需要 Python 3.10+。

```bash
python3 -m pip install esflow faster-whisper imageio-ffmpeg
```

本机还须能找到 `ffmpeg`（系统 PATH 或 `imageio-ffmpeg`）。`local.py` 里的空字符串只表示未配置，不是默认可跑；`MODEL` 空着会直接退出。

## 使用

```bash
SKILL_ROOT="<此 skill 的绝对路径>"

python3 "$SKILL_ROOT/scripts/run.py" --path /path/to/meet.wav --out /path/to/job
# 退出码 2：读 data.brief_path，通读 whole 到最后一句，按下方模板写 draft_path
python3 "$SKILL_ROOT/scripts/run.py" --resume /path/to/job
```

用户明确要求重转才加 `--fresh`。CPU 转写可能数十分钟，日志还在刷就没卡死。

## 参数

| 参数         | 说明                          |
| ---------- | --------------------------- |
| `--path`   | 首次必填。wav 文件，或只含一个 wav 的目录   |
| `--out`    | 首次必填。esflow job 目录；续跑只吃这个目录 |
| `--resume` | TO_AGENT 写完 `meet.md` 后续跑   |
| `--fresh`  | 清空旧稿后整段重转                   |
| `--name`   | 最终总结文件名                     |
| `--schema` | 输出 JSON 契约                  |

## 运行时配置

本机 `scripts/local.py`，空字符串表示未配置。不要把私人路径写进公开仓库。

```python
PYTHON = ""          # 跑本 skill 的解释器，须已装 esflow / faster-whisper
FFMPEG = ""          # 转码用的 ffmpeg
DOWNLOAD_ROOT = ""   # 本地 faster-whisper 模型存放目录
MODEL = ""           # 必填。CT2 路径或 tiny/base/small/medium/large-v3
DEVICE = ""          # 推理设备，如 cpu / cuda
COMPUTE_TYPE = ""    # 计算精度，如 int8 / float16；CPU 常用 int8
```

`MODEL` 填尺寸名且本地没有缓存时，会从网络下载模型到本机 Hugging Face 缓存。中文会议建议 `small` 或以上；`tiny` 同音错误多，总结只能标存疑，不能当逐字稿。

## 副作用边界

- 只写入 `--out` 指定的 job 目录；不删除、不改写源 wav
- 全文落盘后会删除转写过程中的 16k / 切片 wav，源文件不动
- 已有 `export_meet/meet-*.md` 时拒绝覆盖
- 可能访问网络下载 faster-whisper 模型；无鉴权、不收费 API
- `local.py` 仅本机生效，禁止提交私钥、令牌或本机绝对路径

## 输出

```text
<job_dir>/
  transcribe/srt.md
  transcribe/transcript-whole.txt
  agent_digest/meet.md
  export_meet/meet-YYYY-MM-DD.md
```

stdout 一行 JSON `{ok, data, error, meta}`。`to_agent` 时读 `data.brief_path` / `data.draft_path`。不要写 `.esflow/`。

## 节点

```text
resolve_runtime → resolve_source → transcribe → agent_digest → export_meet
```

| id                | 职责                               |
| ----------------- | -------------------------------- |
| `resolve_runtime` | 读 `local.py`，凑齐 ffmpeg 与 whisper |
| `resolve_source`  | 解析 wav 与落盘文件名                    |
| `transcribe`      | 转写，全文落盘后清理过程 wav                 |
| `agent_digest`    | TO_AGENT：按模板写 `meet.md`          |
| `export_meet`     | 落盘 `meet-YYYY-MM-DD.md`，不覆盖已有    |

## 退出码

- `0`：完成
- `1`：运行失败
- `2`：待写 `meet.md`
- `3`：参数或配置无效

## 校正转写，不改事实

中文 whisper 会系统性听错。按上下文校正口语/同音字；**校正后的词必须能在邻近句里讲通**。专名、人名、路径、数量拿不准就标「转写存疑」，禁止猜成具体责任人。

## 按矛盾聚话题，不按发言顺序

先列「会上实际在吵/在问什么」，再合并成 4～10 个话题。标题用冲突本身，不用空泛词。

每条结论都要能指回`srt.md`原句。对不上就删，不要用行业经验填洞。

## 填固定模板

**必须基于会议内容，禁止编造。** 输出骨架（章节名与顺序不得改）：

```markdown
# 会议总结

## 会议主题

## 讨论问题

## 话题一：xxx

### 问题与痛点

### 造成原因

### 方案与建议

## 话题二：xxx

### 问题与痛点

### 造成原因

### 方案与建议

## 待办与落地

## 风险与未决项
```

话题从「话题一」递增。流程变化用文本树，分歧用两列表，不要另开章节。

各节只准写这些：

| 节      | 只写                        | 不准写           |
| ------ | ------------------------- | ------------- |
| 会议主题   | 双方来开会要解决什么                | 会后你认为「应该」解决什么 |
| 讨论问题   | 会上出现过的问题清单                | 你补充的衍生问题      |
| 问题与痛点  | 他们抱怨的现象、数字、例子             | 夸大、脑补后果       |
| 造成原因   | 他们自己给出的原因                 | 你推断的根因框架      |
| 方案与建议  | 会上提议/现有做法/明确反对/未拍板        | 最佳实践、新制度、检查清单 |
| 待办与落地  | 有执行意向的动作；标清谁说了、是否定了负责人/时间 | 把「可以以后做」写成任务  |
| 风险与未决项 | 分歧、未拍板、ASR 存疑专名           | 恐吓式风险清单       |

「方案与建议」三种合法写法：

```text
会上提议 → 写成提议，并写未分工/未拍板
现有做法 → 写成约束或现状，不要包装成新流程
明确反对 → 写成分歧表，不要写成决议
```

会上没说主备负责人、需求卡片、Schema、冻结窗口、发布检查表，就不要出现这些词。

写总结前三条都过，缺一条就停：

```text
read_full → 已读到 transcript-whole.txt 最后一句
     ├→ 每个话题标题能指回至少一段原文时间戳
     └→ 方案/待办用词能在原文搜到；搜不到就删
```

Agent 只写 `draft_path` 的 `meet.md`。

## 红线

- 禁止编造。一句会上没有的方案都不要写
- 禁止把「看起来合理」当成会上共识
- 禁止用已有分析稿替换转写
- 只分析、不改业务代码，不把待办自动变成开发任务
- 涉及裁员、追责、点名：专名存疑必须标明，不写死
