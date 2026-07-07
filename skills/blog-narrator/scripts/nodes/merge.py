"""merge 节点:合成预录音 HTML(audio 内嵌 base64)。

依赖 match(DAG 边),但 accept 只看 gen——match 跳过时 merge 照跑。
body_html/title 复用 parse_md 产物(已 embed_images),audio_sources 按 split 段号读 audio/。
"""

from __future__ import annotations

import base64
import webbrowser
from pathlib import Path

from esflow import Node

import narrator_core
from common import log


class Merge(Node):
    id = "merge"
    title = "合成配音 HTML"

    def accept(self, ctx) -> bool:
        return ctx.get("split") is not None

    def run(self, ctx) -> dict:
        parsed = ctx.get("parse_md")
        split = ctx.get("split")

        work_dir = Path(split["work_dir"])
        audio_dir = Path(split["audio_dir"])
        segment_count = split["segment_count"]

        audio_sources = []
        found = 0
        for i in range(1, segment_count + 1):
            audio_file = None
            for ext in ("mp3", "wav", "m4a", "ogg"):
                candidate = audio_dir / f"{i}.{ext}"
                if candidate.exists():
                    audio_file = candidate
                    break
            if audio_file:
                mime = "audio/mp4" if audio_file.suffix == ".m4a" else f"audio/{audio_file.suffix[1:]}"
                data = base64.b64encode(audio_file.read_bytes()).decode("ascii")
                audio_sources.append(f"data:{mime};base64,{data}")
                found += 1
                log(f"  [{i}] {audio_file.name}")
            else:
                audio_sources.append(None)
                log(f"  [{i}] ⚠️ 缺失")

        output_file = work_dir / f"{parsed['input_stem']}_voice.html"
        html = narrator_core.build_stage_html(
            parsed["title"], parsed["body_html"], audio_sources, 1.0
        )
        output_file.write_text(html, encoding="utf-8")

        if (self.kwargs or {}).get("open", False):
            webbrowser.open(output_file.resolve().as_uri())

        log(f"[merge] {output_file} ({output_file.stat().st_size} bytes) | 音频 {found}/{segment_count}")
        return {
            "html_path": str(output_file),
            "work_dir": str(work_dir),
            "segment_count": segment_count,
            "audio_count": found,
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and Path(artifact["html_path"]).exists())
