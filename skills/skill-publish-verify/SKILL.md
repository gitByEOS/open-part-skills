---
name: skill-publish-verify
description: 发布前黑盒验证。隔离 venv + 路径,agent 以新用户身份读 SKILL.md 自行使用待验 skill,收集 run_record 与产物事实,再由 agent 写可用性报告。任意有 SKILL.md 的 skill 发布前都能跑一遍。用户提到「发布前验证」「skill 黑盒验证」时使用本 skill。
version: 1.1.0
dependencies:
  - python3
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# 发布前黑盒验证

任意有 `SKILL.md` 的 skill 发布前,用一条命令跑完新用户视角的隔离验证,产出
可用性报告。是否 esflow 化不限——`envelope` 契约是 esflow skill 的加成,缺失时
`verify_facts.envelope=null`,agent_report 照常写。

## 依赖

```bash
pip install esflow
```

## 用例格式

```json
{
  "skill_path": "<待验 skill 根目录>",
  "demand": "生成北京南→天津西 2026 抢票日历 HTML"
}
```

只写"验什么 skill + 要完成什么需求"。不含 command、不含 expect——命令由 agent
读 SKILL.md 自行构造,产物是否符合预期由 agent_report 综合判断 + 用户复核。
这是真黑盒,才能测出"新用户能否看懂 SKILL.md"。

## Flow 结构

```text
isolate_env → copy_skill → install_deps → preflight_target → agent_run → verify_artifact → agent_report
                                                    (TO_AGENT)                  (TO_AGENT)
```

| 节点 | 职责 |
|---|---|
| `isolate_env` | 建工作目录 + 全新 python venv |
| `copy_skill` | copy skill 到 work_dir/skill,不动源码 |
| `install_deps` | 优先 `skill/requirements.txt`,否则 frontmatter;pip 全文落 `install_deps.log` |
| `preflight_target` | 验 SKILL.md 可读;有 `scripts/run.py` 则试跑 `--schema` 喂给 brief,失败不 fatal |
| `agent_run` | TO_AGENT:agent 读 SKILL.md 自行用 skill,写 run_record.json |
| `verify_artifact` | 读 run_record + work_dir,全量事实落 `verify_facts.json`,artifact 存摘要 |
| `agent_report` | TO_AGENT:agent 读 facts + SKILL.md 写 `skill_verify_report.md` |

## Agent 介入(两次 --resume)

```bash
# 1. 首跑到 agent_run 退出(exit 2)
python3 scripts/run.py case.json

# 2. Agent 读 _agent_run_brief.json + skill_dir/SKILL.md,自行跑 skill,
#    把 artifacts(必填)+ steps/envelope(可选)写入 run_record.json

# 3. 续跑到 agent_report 退出(exit 2)
python3 scripts/run.py --resume <job_dir>

# 4. Agent 读 _agent_report_brief.json + verify_facts.json + run_record,
#    写 skill_verify_report.md(含:可用性评分/卡壳点/文档问题/产物结论/改进建议)

# 5. 续跑收尾,输出 envelope,极简清理 work_dir
python3 scripts/run.py --resume <job_dir>
```

### agent_run brief 字段

`work_dir/_agent_run_brief.json`:

| 字段 | 说明 |
|---|---|
| `demand` / `work_dir` / `venv_dir` / `python` / `skill_dir` | 需求 + 隔离环境 |
| `installed` / `skipped` / `install_deps_log_path` / `install_deps_source` | 依赖安装结果与日志 |
| `preflight` | `{skill_md_exists, has_run_py, schema_exit_code, schema_stdout_head}` |
| `run_record_file` / `run_record_required_fields` / `run_record_optional_fields` / `run_record_step_fields` | 产物文件名 + 必填/可选字段 + steps 每步字段 |
| `artifacts_must_under` | artifacts 路径必须落在该目录,越界 deliver 失败 |
| `cwd_must_be` / `resume_cmd` | 执行工作目录 + 写完 run_record 后的续跑命令 |

`run_record.json` 必填:`artifacts`(绝对路径列表,全部落在 `artifacts_must_under` 下,
框架核实路径合法性 + 存在性)。可选:`steps`(数组,每步含 `command`/`exit_code`/
`stdout`/`stderr`,agent 自报过程,框架不核实)、`envelope`(skill 最终 envelope)。
单步 skill 可只填 `artifacts`;多步 skill(如自带 TO_AGENT 的 esflow skill)用 `steps`
逐步记录。agent 应主动用 `--out work_dir/out` 之类参数把产物输出到 work_dir 内。

### agent_report brief 字段

`work_dir/_agent_report_brief.json`:`skill_md_path` / `run_record_path` /
`verify_facts_path` / `verify_summary` / `report_file` / `report_required_sections` /
`resume_cmd`。

`skill_verify_report.md` 必含章节:可用性评分、卡壳点、文档问题、产物结论、
改进建议。deliver 逐项检查章节标题,缺失判失败。

### verify_facts.json

全量事实外置,字段:`run_record`(steps/envelope,steps 为 agent 自报过程)、
`envelope_ok`、`artifacts`(`[{path, exists, size, text_head}]`)、`work_dir_tree`。
节点 artifact 与最终 envelope 只带摘要(`exit_code`/`envelope_ok`/`artifact_count`,
`exit_code` 取 steps 末步,无 steps 则 null),避免多 job 时终端被单次 stdout/stderr 撑爆。

## 参数

| 参数 | 说明 |
|---|---|
| `case` | 用例 JSON 路径 |
| `--resume <job_dir>` | 续跑 TO_AGENT 节点 |
| `--keep` | 保留整个 job 目录供人工复核,默认 end/error 后极简清理 |
| `--schema` | 输出 JSON 契约 |

退出码:`0 ok / 1 runtime / 2 to_agent / 3 validation`

## 输出契约

成功时 stdout 一行 JSON envelope(清理后构造,只带仍存在的路径):

```json
{
  "ok": true,
  "data": {
    "work_dir": "<job 目录>",
    "report_path": "<work_dir>/skill_verify_report.md",
    "artifacts": ["<work_dir>/out/xxx.html"],
    "verify": {"exit_code": 0, "envelope_ok": true, "artifact_count": 1}
  },
  "error": null,
  "meta": {"schema_version": "1.1.0", "tool": "skill-publish-verify", "elapsed_ms": 0}
}
```

`artifacts` 是清理后仍存在的产物绝对路径。`verify` 是摘要(全量事实已随
`verify_facts.json` 删除,如需保留用 `--keep`)。失败时 `ok=false`,
`error` 含 `{code, message, retryable}`,`data` 为 null。

## 隔离与生命周期

工作目录 `/tmp/skill-publish-verify/<job_id>`,venv 不复用(每次全新装依赖,
才能暴露 SKILL.md 依赖说明是否完整)。

| 时机 | 动作 |
|---|---|
| `to_agent` 中断 | 不动,还要 --resume |
| `end` / `error` 且非 `--keep` | 只保留 `run_record.artifacts` 指向的产物 + `skill_verify_report.md`,其余全删 |
| `--keep` | 整个 job 目录原样保留 |

清理后无法再 `--resume` 该 job,end/error 后验证已结束,复跑用新 job_id。

## 多场景约定

一 case 一 job,编排层循环,禁止一个 work_dir 跑多轮 demand:

```bash
for f in verify.cases/*.json; do
  python3 scripts/run.py "$f"   # 每次新 job_id、新 work_dir、新 venv
  # Agent 对该 job 完成两次 resume 后再跑下一个 f
done
```

## 仓库约定

待验 skill 在自己仓库下放 `verify.cases/`,每个 JSON 一个 case。Agent SOP 固定
四步:首跑 → 手跑 skill 写 run_record → resume 写报告 → resume 收尾;禁止 resume
别的 job 目录。

## 通用性边界

验任何有 `SKILL.md` 的 skill。有 `scripts/run.py` + `--schema`(esflow skill)
则 preflight 把 schema 摘要喂给 brief、verify 解析 envelope;否则 `envelope=null`
是合法事实,agent 按 SKILL.md 手工执行。不引入分支判断——null 本身就是事实。

被验 skill 若自带 TO_AGENT 节点(如 esflow skill 的 agent_review),agent 须在
`agent_run` 阶段内完整跑通其全部 resume 步骤(首跑到该 skill 的 TO_AGENT 退出 →
写该 skill 要求的产物 → resume 续跑),把最终结果记入 run_record。即两层 TO_AGENT
嵌套时,内层由 agent 自行消化,对 publish-verify 只暴露一次外层 resume。

## Agent 使用指引

用户提到「发布前验证」「skill 黑盒验证」「发布前自检」时使用:确认待验 skill
路径 + demand → 写 case.json → 按"Agent 介入"章节两次 --resume 节奏介入 →
把 `skill_verify_report.md` 呈现给用户。
