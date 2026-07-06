"""agent_run 节点:TO_AGENT,agent 以新用户身份使用 skill。

不实现 run,checkpoint=TO_AGENT。accept 时把 demand + 隔离环境 + 隔离执行契约
写到 work_dir/_agent_run_brief.json,设 output_dir=work_dir。agent 读 brief +
skill_dir/SKILL.md 自行决定怎么跑,把命令/退出码/stdout/stderr/产物/envelope
写入 work_dir/run_record.json。deliver 校验 run_record 存在、含必需字段、
artifacts 路径全部落在 work_dir 内、exit_code 是 int。

关键:用例不提供命令,agent 自己读 SKILL.md 构造——这才是真黑盒,才能测出
"新用户能否看懂 SKILL.md"。
"""

from __future__ import annotations

import json
from pathlib import Path

from esflow import Node, Checkpoint

from common import (
    AGENT_RUN_BRIEF,
    INSTALL_DEPS_LOG,
    RUN_RECORD_FILE,
    log,
)


RUN_RECORD_REQUIRED_FIELDS = ["command", "exit_code", "stdout", "stderr", "artifacts"]


class AgentRun(Node):
    id = "agent_run"
    title = "Agent 使用 skill"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        isolate = ctx.get("isolate_env")
        copy_skill = ctx.get("copy_skill")
        install_deps = ctx.get("install_deps")
        preflight = ctx.get("preflight_target")
        if not isolate or not copy_skill or not install_deps or not preflight:
            return False
        work_dir = Path(isolate["work_dir"])
        self.output_dir = work_dir
        brief = {
            "demand": self.kwargs.get("demand", ""),
            "work_dir": str(work_dir),
            "venv_dir": isolate["venv_dir"],
            "python": isolate["python"],
            "skill_dir": copy_skill["skill_dir"],
            "installed": install_deps.get("installed", []),
            "skipped": install_deps.get("skipped", []),
            "install_deps_log_path": install_deps.get("log_path"),
            "install_deps_source": install_deps.get("source"),
            "preflight": {
                "skill_md_exists": preflight.get("skill_md_exists"),
                "has_run_py": preflight.get("has_run_py"),
                "schema_exit_code": preflight.get("schema_exit_code"),
                "schema_stdout_head": preflight.get("schema_stdout_head"),
            },
            "run_record_file": RUN_RECORD_FILE,
            "run_record_required_fields": RUN_RECORD_REQUIRED_FIELDS,
            "artifacts_must_under": str(work_dir.resolve()),
            "resume_cmd": f"python3 scripts/run.py --resume {work_dir}",
            "cwd_must_be": str(work_dir),
        }
        (work_dir / AGENT_RUN_BRIEF).write_text(
            json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[agent_run] brief -> {work_dir / AGENT_RUN_BRIEF}")
        return True

    def deliver(self, artifact) -> bool:
        files = artifact.get("files", [])
        if RUN_RECORD_FILE not in files:
            return False
        output_dir = Path(artifact["output_dir"])
        try:
            record = json.loads((output_dir / RUN_RECORD_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not all(field in record for field in RUN_RECORD_REQUIRED_FIELDS):
            return False
        if not isinstance(record.get("exit_code"), int):
            return False
        arts = record.get("artifacts")
        if not isinstance(arts, list):
            return False
        # artifacts 路径必须全部落在 work_dir 内,避免产物写到 ~/Downloads 等
        work_root = output_dir.resolve()
        for raw in arts:
            if not Path(str(raw)).resolve().is_relative_to(work_root):
                return False
        return True
