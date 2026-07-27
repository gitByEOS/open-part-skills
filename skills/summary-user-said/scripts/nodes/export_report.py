"""export_report 节点：排他写入 Markdown 与用户发言原文双产物。"""

from __future__ import annotations

import os
from pathlib import Path

from esflow import Node

from common import request_from_dict
from report import render_messages_table, render_report


class ExportReport(Node):
    id = "export_report"
    title = "导出总结与用户发言原文"

    @staticmethod
    def _exclusive_write(path: Path, content: bytes) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def run(self, ctx) -> dict:
        collection = ctx.get("collect_messages")
        validated = ctx.get("validate_summary")
        request = request_from_dict(collection["request"])
        summary_path = Path(request.summary_path)
        original_path = Path(request.original_path)
        existing = [str(path) for path in (summary_path, original_path) if path.exists()]
        if existing:
            raise FileExistsError("目标产物已存在，拒绝覆盖：" + "、".join(existing))

        report = render_report(request, collection, validated["summary"])
        messages_table = render_messages_table(collection)

        self._exclusive_write(original_path, messages_table.encode("utf-8"))
        try:
            self._exclusive_write(summary_path, report.encode("utf-8"))
        except Exception:
            original_path.unlink(missing_ok=True)
            raise

        return {
            "summary_path": str(summary_path),
            "original_path": str(original_path),
            "included": collection.get("stats", {}).get("included", 0),
            "files_scanned": collection.get("stats", {}).get("files_scanned", 0),
            "time_sources": collection.get("time_sources", {}),
            "skipped": {
                key: value
                for key, value in collection.get("stats", {}).items()
                if key in {
                    "json_parse_errors",
                    "empty_text",
                    "outside_window",
                    "non_user_or_unknown",
                    "duplicates_skipped",
                    "timestamp_parse_failed",
                }
            },
        }

    def deliver(self, artifact) -> bool:
        return bool(
            artifact
            and Path(artifact["summary_path"]).is_file()
            and Path(artifact["original_path"]).is_file()
        )
