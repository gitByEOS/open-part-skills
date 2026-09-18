"""resolve_runtime：读 scripts/local.py，凑齐 ffmpeg 与 whisper。"""
from pathlib import Path

from esflow import Node

from runtime_resolve import resolve_runtime


class ResolveRuntime(Node):
    id = "resolve_runtime"
    title = "发现运行时"

    def run(self, ctx) -> dict:
        skill_dir = Path(self.kwargs["skill_dir"]).resolve()
        return resolve_runtime(skill_dir)
