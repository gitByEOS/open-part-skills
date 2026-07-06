---
name: git-review
description: 审查指定范围内的 Git 提交，Agent 逐 commit 评估风险，纯 Python 双索引聚合，输出可视化安全审查报告。当用户需要审查 Git 提交风险或生成安全审查报告时使用
version: 1.1.0
dependencies:
  - "python>=3.10"
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# Git Review

```text
resolve → collect_commits → agent_review(TO_AGENT) → aggregate → export_html
```

## 依赖

```bash
pip install esflow
```

## 快速使用

```bash
python3 scripts/run.py --repo /path/to/repo --scope 2026-05-01..2026-05-07
python3 scripts/run.py --repo /path/to/repo --scope main..dev
python3 scripts/run.py --repo /path/to/repo --scope main
```

输出到 `<out>/<scope_id>/`：

| 文件 | 说明 |
|---|---|
| `commits.json` | collect_commits 产物 |
| `review.json` | Agent 写,逐 commit 风险评估 |
| `aggregate.json` | 双索引聚合结果 |
| `process.md` | 人读过程记录 |
| `security_report.html` | 可视化报告 |

`review.json` 由 Agent 读 `assets/vigil.md` + `commits.json` 生成。

> 默认输出 `/tmp/git-review/`，高频操作不占用户目录。TO_AGENT resume 依赖 work_dir 存活，`/tmp` 被清理后 resume 会丢，需尽快 resume 或显式 `--out` 到持久目录。

### scope 日期边界

`--scope since..until` 日期模式：`since` 含当天零点，`until` 含当天 23:59:59。如 `2026-07-03..2026-07-05` 抓 7-03 00:00 到 7-05 23:59 的 commit。

## Flow 结构

esflow DAG 编排（`scripts/flow.py` 声明，`scripts/nodes/` 各节点）：

| 节点 | 职责 |
|---|---|
| `resolve` | 解析 repo/scope，建 work_dir，产出 plan |
| `collect_commits` | 跑 git log，结构化 commits.json |
| `agent_review` | TO_AGENT 节点，跑到它退出进程（exit 2），Agent 写 review.json 后续跑 |
| `aggregate` | 纯 Python 双索引聚合（作者风险榜 + commit 风险明细），产出 aggregate.json + process.md |
| `export_html` | 从 aggregate.json 渲染 security_report.html |

### work_dir 与 job_dir

- **work_dir** = `<out>/<scope_id>/`，业务产物目录
- **job_dir** = `<out>/.esflow-jobs/git-review/<timestamp>/`，esflow 框架目录（节点 artifact + `_break_to_agent.json` + `_flow_dir.txt`）
- TO_AGENT 退出时 stdout envelope 携带 `work_dir / commits / vigil_md`，Agent 解析 stdout 拿接管路径
- `--resume <job_dir>` 传 job_dir（非 work_dir）

## Agent 介入

```bash
# 1. 首跑到 agent_review 退出(exit 2)
python3 scripts/run.py --repo /path/to/repo --scope 2026-05-01..2026-05-07
# stdout envelope: {ok:true, data:{work_dir, commits(commits.json 路径), vigil_md, commits_count}}
# stderr: [to_agent] 完成后续跑:python3 scripts/run.py --resume <job_dir>

# 2. Agent 读 data.vigil_md + data.commits,按 vigil 规则逐 commit 评估
#    写 data.work_dir/review.json (schema 见下方)

# 3. 续跑聚合 + HTML
python3 scripts/run.py --resume <job_dir>
```

TO_AGENT 退出时 envelope.data 只含 `work_dir/commits/vigil_md/commits_count`（产物未生成）；续跑聚合后最终 envelope.data 才含 `reviews/report/process_md`（见 `--schema`）。

## review.json Schema

写到 `work_dir/review.json`，框架 deliver 严格校验值类型：

```json
{
  "reviews": [
    {
      "hash": "commit sha",
      "author": "提交者",
      "risk_level": "P0|P1|P2|P3|P4|P5",
      "risk_summary": "会造成什么后果",
      "files": ["path/to/file:起始行-结束行"],
      "fix_suggestion": "可执行的修改建议",
      "time": "提交时间 ISO",
      "subject": "提交标题",
      "cause": "造成风险原因"
    }
  ]
}
```

**必填 6 字段**：`hash / author / risk_level / risk_summary / files / fix_suggestion`
**可选 3 字段**：`time / subject / cause`（建议都填，process.md 才不空列）

约束：`risk_level` 只能 P0-P5；`files` 是字符串数组，元素格式 `path:起-止`；deliver 失败 stderr 会提示缺哪个字段，修复后 `--resume` 续跑。完整规则见 `assets/vigil.md`。

## 参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--repo <path>` | `.` | 被审查的 git 仓库 |
| `--scope <range>` | - | 日期 `since..until` / 分支 `b1..b2` / 单分支 |
| `--out <dir>` | `/tmp/git-review` | 输出根目录 |
| `--resume <job_dir>` | - | 续跑 TO_AGENT 节点 |
| `--max-count <n>` | `0` | 单分支模式最多抓多少 commit,0 不限 |
| `--no-open` | false | 不弹浏览器,给 CI/无头环境 |
| `--dry-run` | false | 只跑 resolve 产出 plan |
| `--schema` | false | 输出 JSON 契约 |

退出码：`0 ok / 1 runtime / 2 to_agent / 3 validation / 4 auth`

## 硬性规则

- `security_report.html` 由 `nodes/export_html.py` 生成，避免样式漂移
- 审查代码只读，不修改被审查业务代码
- 每次 review.json 写到独立 work_dir，不覆盖历史报告
- `assets/vigil.md` 是 Agent 角色设定与 schema 完整说明，agent_review 节点执行前必须读
