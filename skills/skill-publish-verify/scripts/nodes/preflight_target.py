"""preflight_target 节点:install_deps 后、agent_run 前预检待验 skill 可用性。

通用化预检,不要求待验 skill 是 esflow skill:
- SKILL.md 必须可读(双重兜底,case_schema + copy_skill 已保证)
- scripts/run.py 不存在不 fatal:记 has_run_py=false,agent 按纯 prompt skill 处理
- scripts/run.py 存在则试跑 --schema:exit 0 把 schema_stdout_head 喂给 agent_run brief
  帮 agent 更快理解 skill 契约;非 0 只记 schema_exit_code,不 raise

esflow skill 的 --schema 契约是加成,不是验证前提。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log


class PreflightTarget(Node):
    id = "preflight_target"
    title = "预检待验 skill"

    def run(self, ctx) -> dict:
        isolate = ctx.get("isolate_env")
        copy_skill = ctx.get("copy_skill")
        install_deps = ctx.get("install_deps")
        if not isolate or not copy_skill or not install_deps:
            raise CliError("preflight_error", "上游节点产物缺失", EXIT_VALIDATION)
        python = Path(isolate["python"])
        skill_dir = Path(copy_skill["skill_dir"])
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise CliError(
                "preflight_error",
                f"待验 skill 缺 SKILL.md:{skill_md}",
                EXIT_VALIDATION,
            )

        skill_run = skill_dir / "scripts" / "run.py"
        artifact = {
            "skill_md_exists": True,
            "has_run_py": skill_run.is_file(),
            "schema_exit_code": None,
            "schema_stdout_head": None,
            "install_deps_log_path": install_deps.get("log_path"),
        }

        if not skill_run.is_file():
            log(f"[preflight_target] SKILL.md ok, 无 scripts/run.py(纯 prompt skill)")
            return artifact

        result = subprocess.run(
            [str(python), str(skill_run), "--schema"],
            check=False, capture_output=True, text=True,
        )
        artifact["schema_exit_code"] = result.returncode
        if result.returncode == 0:
            artifact["schema_stdout_head"] = result.stdout.strip()[:500]
            log(f"[preflight_target] SKILL.md ok + --schema ok (python={python.name})")
        else:
            log(f"[preflight_target] SKILL.md ok + --schema 退出 {result.returncode}(非 esflow skill,放行)")
        return artifact

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("skill_md_exists") is True)
