"""export 节点:合并 format_table 表格 + agent_advice 建议,落盘最终报告。"""

from pathlib import Path

from esflow import Node

from weather_domain import ADVICE_FILENAME


def _format_advice(advice_text: str) -> str:
    if not advice_text:
        return ""
    if advice_text.startswith("## "):
        return advice_text
    if advice_text.lstrip().startswith("|"):
        return "## 外出建议\n\n" + advice_text
    return "## 外出建议\n\n" + advice_text


class Export(Node):
    id = "export"
    title = "落盘最终报告"

    def run(self, ctx) -> dict:
        table = ctx.get("format_table")
        advice_art = ctx.get("agent_advice")

        advice_text = ""
        if advice_art and ADVICE_FILENAME in advice_art.get("files", []):
            advice_path = Path(advice_art["output_dir"]) / ADVICE_FILENAME
            advice_text = advice_path.read_text(encoding="utf-8").strip()

        final = table["markdown"].rstrip() + "\n"
        if advice_text:
            final += f"\n{_format_advice(advice_text)}\n"

        out_dir = Path(self.kwargs.get("out_dir") or self.output_dir).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "weather_report.md"
        path.write_text(final, encoding="utf-8")
        return {
            "out_path": str(path),
            "out_dir": str(out_dir),
            "chars": len(final),
            "has_advice": bool(advice_text),
        }
