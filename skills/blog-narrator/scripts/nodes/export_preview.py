"""export_preview 节点:轻量预览 HTML,无预录音,体积小。

仅 mode=preview 时跑;mode=tts 时 accept False 跳过。
"""

from __future__ import annotations

import webbrowser
from pathlib import Path

from esflow import Node

import narrator_core
from common import CliError, EXIT_VALIDATION, log


class ExportPreview(Node):
    id = "export_preview"
    title = "生成轻量预览 HTML"

    def accept(self, ctx) -> bool:
        if (self.kwargs or {}).get("mode") != "preview":
            return False
        return ctx.get("parse_md") is not None

    def run(self, ctx) -> dict:
        parsed = ctx.get("parse_md")
        kw = self.kwargs or {}
        output_path = Path(kw["output"]).expanduser().resolve()
        rate = float(kw.get("rate", 1.15))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        html = narrator_core.build_stage_html(parsed["title"], parsed["body_html"], rate=rate)
        output_path.write_text(html, encoding="utf-8")

        if kw.get("open", False):
            webbrowser.open(output_path.resolve().as_uri())

        log(f"[export_preview] {output_path} ({output_path.stat().st_size} bytes)")
        return {"html_path": str(output_path)}

    def deliver(self, artifact) -> bool:
        return bool(artifact and Path(artifact["html_path"]).exists())
