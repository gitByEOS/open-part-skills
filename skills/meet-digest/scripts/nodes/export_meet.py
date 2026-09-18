"""export_meet：按日期链把草稿写成最终 meet-YYYY-MM-DD.md。"""
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, MEET_DRAFT


class ExportMeet(Node):
    id = "export_meet"
    title = "落盘会议总结"

    def run(self, ctx) -> dict:
        transcribe = ctx.get("transcribe")
        digest = ctx.get("agent_digest")
        if not transcribe or not digest:
            raise CliError("export_missing", "缺少转写或总结产物", EXIT_VALIDATION)
        draft = Path(digest["output_dir"]) / MEET_DRAFT
        text = draft.read_text(encoding="utf-8")
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(
            p for p in out_dir.iterdir() if p.is_file() and (
                p.name == "meet.md" or p.name.startswith("meet-") and p.name.endswith(".md")
            )
        )
        if existing:
            raise CliError(
                "meet_exists",
                f"不覆盖已有 {existing[0].name}，除非用户明确要求覆盖",
                EXIT_VALIDATION,
            )
        dest = out_dir / transcribe["meet_name"]
        dest.write_text(text, encoding="utf-8")
        return {
            "meet_path": str(dest),
            "wav": transcribe["wav"],
            "srt": transcribe["srt"],
            "whole": transcribe["whole"],
        }
