"""collect_messages 节点：解析、归窗并落盘原始消息流。"""

from pathlib import Path

from esflow import Node

from common import MESSAGES_FILENAME, request_from_dict
from history import SourceFile, collect_messages


class CollectMessages(Node):
    id = "collect_messages"
    title = "收集用户发言原文"

    def run(self, ctx) -> dict:
        upstream = ctx.get("discover_sources")
        request = request_from_dict(upstream["request"])
        files = [
            SourceFile(
                source_id=item["source_id"],
                source_type=item["source_type"],
                root_label=item["root_label"],
                path=Path(item["path"]),
                relative_path=item["relative_path"],
            )
            for item in upstream["files"]
        ]
        output_path = self.output_dir / MESSAGES_FILENAME
        collection = collect_messages(files, request, output_path)
        collection["request"] = request.as_dict()
        collection["discovery"] = upstream["discovery"]
        return collection

    def deliver(self, artifact) -> bool:
        return bool(artifact and Path(artifact["messages_path"]).is_file())
