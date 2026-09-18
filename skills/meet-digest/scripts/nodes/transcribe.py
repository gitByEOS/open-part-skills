"""transcribe：切片识别，产物写本节点 output_dir。"""
from pathlib import Path

from esflow import Node

from transcribe_lib import transcribe_wav


class Transcribe(Node):
    id = "transcribe"
    title = "转写会议"

    def run(self, ctx) -> dict:
        runtime = ctx.get("resolve_runtime")
        source = ctx.get("resolve_source")
        result = transcribe_wav(
            Path(source["wav"]),
            Path(self.output_dir),
            runtime,
            bool(source.get("fresh")),
        )
        result["wav"] = source["wav"]
        result["meet_name"] = source["meet_name"]
        return result

    def deliver(self, artifact) -> bool:
        whole = Path(artifact.get("whole") or "")
        return whole.is_file() and whole.stat().st_size > 0
