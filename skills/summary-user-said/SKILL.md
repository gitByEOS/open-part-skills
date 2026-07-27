---
name: summary-user-said
description: >-
  只读汇总本机 Cursor、Claude Code、Codex 或指定目录中的用户发言，按完整自然日或自然周生成带证据引用的总结与原文双 Markdown 产物。脚本固定数据源、筛选 schema 和时间窗，Agent 只总结筛选结果；用户提到“回顾最近说过什么”“整理历史目标、约束、决策或验收项”时使用。
version: 1.0.0
dependencies:
  - "python>=3.10"
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# Summary User Said

只读扫描已选择的本地会话 JSONL，输出可追溯的用户发言总结和原文表。脚本负责数据源、schema、时间窗、去重、证据与落盘；Agent 只根据脚本筛选后的 `messages.jsonl` 写摘要。

## 输入 → DAG → 产物

```text
validate_request(CLI)
  ├────→ --cursor ──┐
  ├────→ --claude ──┤
  ├────→ --codex ───┼→ discover_sources → collect_messages
  └────→ --dir ─────┘                         │
                                              ├→ 有消息 → agent_summary(TO_AGENT)
                                              │              ↓
                                              └→ 无消息 → agent_summary(skip)
                                                             ↓
                                              validate_summary → export_report
                                                                      ├→ 当前路径/<base>.md
                                                                      └→ 当前路径/<base>.messages.md
```

> **隐私与读取边界**：本 skill 不联网、不上传、不修改源 JSONL、代码或 Git 状态。它不会脱敏，筛选后的原文会交给 Agent 并写入本地产物；只应在受信任目录运行。`user` 仅是源记录声明的角色，不证明真实发言者身份。

## 使用

```bash
SKILL_ROOT="<此 skill 的绝对路径>"

# 默认：Cursor + 前一个完整自然周
python3 "$SKILL_ROOT/scripts/run.py"

# 单个或组合内置源
python3 "$SKILL_ROOT/scripts/run.py" --cursor --day 3
python3 "$SKILL_ROOT/scripts/run.py" --claude --week 2
python3 "$SKILL_ROOT/scripts/run.py" --cursor --claude --codex --day 7

# 指定目录：自动识别 Cursor、Claude、Codex 的已知 JSONL schema
python3 "$SKILL_ROOT/scripts/run.py" --dir /path/to/history --week 1
```

有匹配消息时，首跑会在 `agent_summary` 暂停并返回 exit 2：

```bash
# 1. 读取 envelope.data.brief_path 和 messages_path
# 2. 只读取 messages_path，按 brief 写 agent_summary_path
# 3. 用 envelope.data.resume_command 续跑并生成双产物
python3 "$SKILL_ROOT/scripts/run.py" --resume <job_dir>
```

无匹配消息时不暂停，直接生成写明“无匹配 user 发言”的双产物。

## 参数

| 参数 | 说明 |
| --- | --- |
| `--cursor` | 读取 `~/.cursor/projects/**/*.jsonl`；可与 `--claude`、`--codex` 组合 |
| `--claude` | 读取 `~/.claude/projects/**/*.jsonl` |
| `--codex` | 读取 `~/.codex/sessions/**/*.jsonl` |
| `--dir <DIR>` | 自定义历史根目录；与三个内置源互斥 |
| `--day <N>` | 前 N 个完整自然日；N 必须为正整数，与 `--week` 互斥 |
| `--week <N>` | 前 N 个完整 ISO 自然周；默认 `1` |
| `--resume <JOB_DIR>` | 续跑等待 Agent 的 job；必须独占 |
| `--schema` | 输出 JSON 契约；必须独占 |

未选择数据源时默认 `--cursor`。重复数据源、重复 `--dir`、无效范围或产物冲突都会在扫描前失败，不创建 job、不读取历史、不覆盖文件。

## 数据源与读取边界

| 源 | 授权根目录 | 仅接受的用户记录 |
| --- | --- | --- |
| Cursor | `~/.cursor/projects/` | 顶层 `role: user`，且 `message.content[].type=text` |
| Claude Code | `~/.claude/projects/` | 顶层 `type: user`，且 `message.role: user` |
| Codex | `~/.codex/sessions/` | `event_msg/user_message`；旧会话无前者时才读取 `response_item/message/role=user` |
| `--dir` | 用户指定目录 | 逐行仅识别上述 schema |

脚本会解析授权根目录、只发现其内部常规 `.jsonl` 文件并拒绝符号链接；发现统计会写入 job artifact 和首跑 envelope。未知 schema、assistant/system/developer/tool 内容不会进入 `messages.jsonl`。

额外筛除：

- Cursor 固定收尾提示与同会话重复消息
- Claude 跨会话转发、上下文续写摘要和请求中断事件
- Codex 拼接的 QQ 回传、产物/环境/网关/待办/浏览器规则、团队委派、`.codex-team` 以及 `<soul>` 角色设定
- 窗口外、空文本、时间无法定位或证据重复的消息

时间优先级：Cursor 文本内 `<timestamp>`、Claude/Codex 结构化 ISO 时间、源 JSONL 的 mtime fallback。每条消息独立判定，不继承同文件其他记录的时间。

## 输出与生命周期

- stdout 只输出一行 JSON envelope `{ok, data, error, meta}`；esflow 事件和 Agent 指引写 stderr
- 有消息的首跑：`data.status=to_agent`，并给出 `brief_path`、唯一允许 Agent 读取的 `messages_path`、`agent_summary_path` 与续跑命令
- 完成：`data.status=end`，含正式产物路径、筛选统计和不变量检查
- job 保存流程 artifact；正式产物直接写入**执行命令时的当前目录**：

```text
<source-set>-<day|week>-<start-date>_to_<end-date>.md
<source-set>-<day|week>-<start-date>_to_<end-date>.messages.md
```

- `.md`：范围、筛选统计、周期总览、要点、决策与待办、分周期摘要、反复主题
- `.messages.md`：按时间升序的 `| 时间 | 内容 |` 原文表
- 自定义目录的 `source-set` 为路径短哈希，不暴露自定义绝对路径
- 两项正式产物以 `0600` 排他创建；任一目标已存在即拒绝整个运行，绝不覆盖

每个摘要条目必须引用至少一个 `source-id:line`。周期条目只能引用同周期消息；关键决策/待办只能是 `pending`、`blocked` 或 `confirmed`；不存在、重复或跨周期的证据会让续跑失败。

## 节点(5 个)

| id | depth | 职责 |
| --- | ---: | --- |
| `discover_sources` | 0 | 解析授权根目录，只发现根目录内常规 JSONL，记录发现审计 |
| `collect_messages` | 1 | 按已知 schema 提取 user 文本、归窗、去重并写 `messages.jsonl` |
| `agent_summary` | 2 | 有消息时 TO_AGENT；brief 限定 Agent 只读 `messages.jsonl` |
| `validate_summary` | 3 | 校验消息计数、周期归属、摘要结构和证据 |
| `export_report` | 4 | 排他写入总结与原文双产物 |


## 退出码

- `0`：双产物已完成
- `1`：运行时错误
- `2`：等待 Agent 写 `summary.json`
- `3`：参数、路径、产物冲突或业务校验失败

## 依赖

```bash
pip install esflow
```

Python 需要 3.10 或更高版本。发布前可运行：

```bash
python3 test/test_summary_user_said.py -v
python3 -m compileall -q skills/summary-user-said/scripts
```
