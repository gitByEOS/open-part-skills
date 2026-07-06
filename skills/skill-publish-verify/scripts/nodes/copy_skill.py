"""copy_skill 节点:把待验 skill 整树 copy 到 work_dir/skill,避免动源码。"""

from __future__ import annotations

import shutil
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log


class CopySkill(Node):
    id = "copy_skill"
    title = "复制 skill 包"

    def run(self, ctx) -> dict:
        isolate = ctx.get("isolate_env")
        work_dir = Path(isolate["work_dir"])
        skill_src = Path(self.kwargs["skill_path"]).expanduser()
        if not skill_src.is_dir():
            raise CliError("copy_error", f"skill 源目录不存在:{skill_src}", EXIT_VALIDATION)
        skill_dir = work_dir / "skill"
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(skill_src, skill_dir)
        log(f"[copy_skill] -> {skill_dir}")
        return {"skill_dir": str(skill_dir)}

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("skill_dir"))
