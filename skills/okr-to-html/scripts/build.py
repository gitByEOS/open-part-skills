#!/usr/bin/env python3
"""将 OKR 文本/Markdown 生成为单页 HTML。用法: python3 build.py input.md -o output.html"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_ROOT / "assets" / "template.html"

OBJ_HEADING = re.compile(
    r"^##\s+O(\d+)\s*(?:·|\.|-)\s*(.+?)\s*$",
    re.IGNORECASE,
)
WEIGHT_TAIL = re.compile(r"\|\s*(?:权重\s*)?(\d+)\s*%\s*$")


@dataclass
class KeyResult:
    text_html: str
    weight: str


@dataclass
class Objective:
    index: int
    tab_label: str
    label: str
    key_results: list[KeyResult] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return f"o{self.index}"


@dataclass
class OkrDocument:
    page_title: str
    heading: str
    accent: str | None
    subtitle: str
    objectives: list[Objective]


def parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    if not lines or lines[0].strip() != "---":
        return {}, lines
    meta: dict[str, str] = {}
    body_start = 1
    for i in range(1, len(lines)):
        line = lines[i].strip()
        if line == "---":
            body_start = i + 1
            break
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip().lower()] = val.strip()
    return meta, lines[body_start:]


def inline_markdown_to_html(text: str) -> str:
    """仅支持 **粗体** 与行内转义"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            inner = html.escape(part[2:-2])
            out.append(f"<strong>{inner}</strong>")
        else:
            out.append(html.escape(part))
    return "".join(out)


def split_kr_line(line: str) -> tuple[str, str]:
    m = WEIGHT_TAIL.search(line)
    if not m:
        raise ValueError(f"KR 行缺少权重（示例: ... | 40%）: {line}")
    weight = f"{m.group(1)}%"
    text = line[: m.start()].strip()
    if text.startswith("- "):
        text = text[2:].strip()
    return text, weight


def format_heading(heading: str, accent: str | None) -> str:
    if accent and accent in heading:
        idx = heading.index(accent)
        before = html.escape(heading[:idx])
        after = html.escape(heading[idx + len(accent) :])
        mid = html.escape(accent)
        return f"{before}<span class=\"accent\">{mid}</span>{after}"
    return html.escape(heading)


def parse_content(raw: str) -> OkrDocument:
    lines = raw.replace("\r\n", "\n").split("\n")
    meta, body_lines = parse_frontmatter(lines)

    page_title = meta.get("title", "OKR")
    heading = meta.get("heading", page_title)
    accent = meta.get("accent") or None
    subtitle = meta.get("subtitle", "")

    objectives: list[Objective] = []
    current: Objective | None = None

    for raw_line in body_lines:
        line = raw_line.strip()
        if not line:
            continue

        # 无 frontmatter 时允许 # 主标题
        if line.startswith("# ") and not objectives:
            heading = line[2:].strip()
            if not page_title or page_title == "OKR":
                page_title = heading
            continue

        # 无 frontmatter 时允许 > 副标题
        if line.startswith("> ") and not subtitle:
            subtitle = line[2:].strip()
            continue

        # ## On · 标签 开启一个 Objective
        m = OBJ_HEADING.match(line)
        if m:
            if current:
                objectives.append(current)
            current = Objective(
                index=int(m.group(1)),
                tab_label=m.group(2).strip(),
                label="",
            )
            continue

        # KR 行：- 描述 | 权重 NN%
        if line.startswith("- "):
            if not current:
                raise ValueError(f"KR 行缺少所属 Objective: {line}")
            text, weight = split_kr_line(line)
            current.key_results.append(
                KeyResult(text_html=inline_markdown_to_html(text), weight=weight)
            )
            continue

        # Objective 标题下首行非列表 = O 描述
        if current and not current.label and not current.key_results:
            current.label = line
            continue

        raise ValueError(f"无法解析的行: {raw_line}")

    if current:
        objectives.append(current)

    if not objectives:
        raise ValueError("未解析到任何 Objective（需要 ## O1 · 标签）")

    for obj in objectives:
        if not obj.label:
            raise ValueError(f"O{obj.index} 缺少目标描述")
        if not obj.key_results:
            raise ValueError(f"O{obj.index} 至少一条 KR")

    return OkrDocument(
        page_title=page_title,
        heading=heading,
        accent=accent,
        subtitle=subtitle,
        objectives=objectives,
    )


def render_kr(kr: KeyResult) -> str:
    return f"""                    <li class="kr-item">
                        <span class="kr-dot"></span>
                        <div class="kr-content">
                            <span class="kr-text">{kr.text_html}</span>
                            <span class="kr-weight">
                                <span class="kr-weight-label">权重</span>
                                <span class="kr-weight-value">{html.escape(kr.weight)}</span>
                            </span>
                        </div>
                    </li>"""


def render_card(obj: Objective, is_active: bool) -> str:
    active = " is-active" if is_active else ""
    card_class = f"card-o{((obj.index - 1) % 3) + 1}"
    krs = "\n".join(render_kr(kr) for kr in obj.key_results)
    label = html.escape(obj.label)
    kr_count = len(obj.key_results)
    if kr_count <= 3:
        fill_class = " is-fill"
    elif kr_count <= 6:
        fill_class = " is-grow"
    else:
        fill_class = ""
    dense_class = " is-dense" if kr_count >= 6 else ""
    scroll_class = " is-scrollable" if kr_count > 6 else ""
    return f"""            <div class="okr-card {card_class}{active}" data-okr="{obj.slug}">
                <div class="gloss"></div>
                <div class="card-header">
                    <div class="card-number">O{obj.index}</div>
                    <div class="card-o-label">{label}</div>
                </div>
                <div class="kr-scroll{scroll_class}">
                <ul class="kr-list{fill_class}{dense_class}">
{krs}
                </ul>
                </div>
            </div>"""


def render_tab(obj: Objective, is_active: bool) -> str:
    sd = f"sd{((obj.index - 1) % 3) + 1}"
    active = " is-active" if is_active else ""
    selected = "true" if is_active else "false"
    tab_text = html.escape(f"O{obj.index} · {obj.tab_label}")
    return f"""            <button type="button" class="summary-item summary-tab{active}" role="tab" aria-selected="{selected}" data-okr="{obj.slug}">
                <span class="summary-dot {sd}"></span> {tab_text}
            </button>"""


def cards_grid_class(objectives: list[Objective]) -> str:
    """按最大 KR 条数分档返回卡片网格高度类，≤4 统一基础高度铺满，5+ 转多档"""
    max_kr = max(len(obj.key_results) for obj in objectives)
    if max_kr >= 5:
        return "cards-grid--multi"
    return "cards-grid--four"


def build_html(doc: OkrDocument) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    cards = "\n".join(
        render_card(obj, i == 0) for i, obj in enumerate(doc.objectives)
    )
    tabs = "\n".join(
        render_tab(obj, i == 0) for i, obj in enumerate(doc.objectives)
    )
    order = json.dumps([obj.slug for obj in doc.objectives], ensure_ascii=False)
    grid_class = cards_grid_class(doc.objectives)

    return (
        template.replace("__PAGE_TITLE__", html.escape(doc.page_title))
        .replace("__HEADER_TITLE__", format_heading(doc.heading, doc.accent))
        .replace("__SUBTITLE__", html.escape(doc.subtitle))
        .replace("__CARDS_GRID_CLASS__", grid_class)
        .replace("__CARDS__", cards)
        .replace("__TABS__", tabs)
        .replace("__OKR_ORDER__", order)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="OKR 文本/Markdown → HTML")
    parser.add_argument("input", type=Path, nargs="?", help="输入 .md/.txt；省略则从 stdin 读取")
    parser.add_argument("-o", "--output", type=Path, help="输出 HTML 路径")
    args = parser.parse_args()

    if args.input:
        raw = args.input.read_text(encoding="utf-8")
        default_out = args.input.with_suffix(".html")
    else:
        raw = sys.stdin.read()
        default_out = Path("okr.html")

    doc = parse_content(raw)
    html_out = build_html(doc)
    out_path = args.output or default_out
    out_path.write_text(html_out, encoding="utf-8")
    print(out_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
