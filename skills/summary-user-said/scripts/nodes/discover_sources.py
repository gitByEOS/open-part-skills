"""discover_sources 节点：只发现授权 JSONL，不读取正文。"""

from esflow import Node

from common import request_from_dict
from history import discover_source_files


class DiscoverSources(Node):
    id = "discover_sources"
    title = "发现历史文件"

    def run(self, ctx) -> dict:
        request = request_from_dict(self.kwargs["request"])
        files, discovery = discover_source_files(request)
        return {
            "request": request.as_dict(),
            "discovery": discovery,
            "files": [
                {
                    "source_id": item.source_id,
                    "source_type": item.source_type,
                    "root_label": item.root_label,
                    "path": str(item.path),
                    "relative_path": item.relative_path,
                }
                for item in files
            ],
        }
