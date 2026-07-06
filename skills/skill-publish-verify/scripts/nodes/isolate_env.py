"""isolate_env 节点:建工作目录 + 全新 python venv。

work_dir 由 run.py 经 node_args 注入(= esflow job_dir),保证 per-node
artifact.json 与 run_record/report 同住一个目录。venv 不复用,每次全新装依赖
才能暴露 SKILL.md 依赖说明是否完整。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_RUNTIME, log


def create_venv(venv_dir):
    """用当前 python 创建 venv,返回 venv 内 python 路径。"""
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise CliError(
            "isolate_error",
            f"创建 venv 失败:{result.stderr.strip() or result.stdout.strip()}",
            EXIT_RUNTIME, retryable=True,
        )
    python = venv_dir / "bin" / "python"
    if not python.exists():
        raise CliError("isolate_error", f"venv 未生成 python:{python}", EXIT_RUNTIME)
    return python


class IsolateEnv(Node):
    id = "isolate_env"
    title = "建隔离环境"

    def run(self, ctx) -> dict:
        work_dir = Path(self.kwargs["work_dir"])
        work_dir.mkdir(parents=True, exist_ok=True)
        venv_dir = work_dir / "venv"
        python = create_venv(venv_dir)
        log(f"[isolate_env] work_dir={work_dir} venv={venv_dir}")
        return {
            "work_dir": str(work_dir),
            "venv_dir": str(venv_dir),
            "python": str(python),
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("python"))
