"""resolve_source：唯一 wav 与落盘文件名。"""
from pathlib import Path

from esflow import Node

from domain import meet_filename, resolve_wav


class ResolveSource(Node):
    id = "resolve_source"
    title = "解析会议源"

    def run(self, ctx) -> dict:
        wav = resolve_wav(Path(self.kwargs["path"]).expanduser().resolve())
        name = meet_filename(wav, self.kwargs.get("name"))
        return {
            "wav": str(wav),
            "meet_name": name,
            "fresh": bool(self.kwargs.get("fresh")),
        }
