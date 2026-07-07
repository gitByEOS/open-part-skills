"""split 节点:分段导出 work_dir/src.md + srt.md + audio/。

仅 mode=tts 时跑。texts 来自 parse_md,src.md 从原始 md 重读写入(供 merge 复原)。
"""

from __future__ import annotations

import re
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log


class Split(Node):
    id = "split"
    title = "分段导出 srt"

    def accept(self, ctx) -> bool:
        if (self.kwargs or {}).get("mode") != "tts":
            return False
        return ctx.get("parse_md") is not None

    def run(self, ctx) -> dict:
        parsed = ctx.get("parse_md")
        kw = self.kwargs or {}
        work_dir = Path(kw["work_dir"]).expanduser().resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "audio").mkdir(exist_ok=True)

        input_path = Path(parsed["input_path"])
        md_text = input_path.read_text(encoding="utf-8")
        (work_dir / "src.md").write_text(md_text, encoding="utf-8")

        texts = parsed["texts"]
        lines = [f"# 共 {len(texts)} 段\n\n"]
        for i, text in enumerate(texts, 1):
            if not re.search(r"[a-zA-Z一-鿿0-9]", text):
                lines.append(f"## [{i}] ⚪ （跳过空行）\n\n")
            else:
                lines.append(f"## [{i}]\n\n{text}\n\n")

        srt_path = work_dir / "srt.md"
        srt_path.write_text("".join(lines), encoding="utf-8")

        log(f"[split] {srt_path} | 共 {len(texts)} 段")
        return {
            "work_dir": str(work_dir),
            "srt_path": str(srt_path),
            "audio_dir": str(work_dir / "audio"),
            "segment_count": len(texts),
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and Path(artifact["srt_path"]).exists())
