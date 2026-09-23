#!/usr/bin/env python3
"""把缩进列表结构的 Markdown 转成单文件可视化网页"""
import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def parse_markdown(text):
    """标题/引言/缩进列表 → 树；多根时包虚拟根"""
    title, intro, roots, stack = "", [], [], []
    for raw in text.splitlines():
        line = raw.expandtabs(2).rstrip()
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            node = {"text": m.group(2).strip(),
                    "depth": len(m.group(1)) // 2,
                    "children": []}
            while stack and stack[-1]["depth"] >= node["depth"]:
                stack.pop()
            (stack[-1]["children"] if stack else roots).append(node)
            stack.append(node)
            continue
        if not roots and line.strip():
            intro.append(re.sub(r"^>\s?", "", line.strip()))
    if not roots:
        sys.exit("错误：未解析到任何列表节点，输入需为缩进列表结构")
    root = roots[0] if len(roots) == 1 else {
        "text": title or "文档大纲", "depth": -1, "children": roots}
    return {"title": title or root["text"], "intro": intro, "root": root}


def render(data, theme, footer):
    """读 assets 模板与静态资源，内联为单文件 HTML"""
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    css = (ASSETS / "viewer.css").read_text(encoding="utf-8")
    js = (ASSETS / "viewer.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    parts = {
        "TITLE": html.escape(data["title"]), "CSS": css, "JS": js,
        "DATA": payload, "FOOTER": html.escape(footer), "THEME": theme,
    }
    return re.sub(r"\{\{(TITLE|CSS|JS|DATA|FOOTER|THEME)\}\}",
                  lambda match: parts[match.group(1)], template)


def main():
    ap = argparse.ArgumentParser(description="Markdown 缩进列表 → 可视化网页")
    ap.add_argument("input", help="输入 Markdown 文件")
    ap.add_argument("-o", "--output", help="输出 HTML 路径")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        sys.exit(f"错误：文件不存在 {src}")
    data = parse_markdown(src.read_text(encoding="utf-8"))

    out = Path(args.output) if args.output else src.with_suffix(".mindmap.html")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    footer = f"源文件 {src.name} · 生成于 {now} · 由 mindmap 生成"
    out.write_text(render(data, args.theme, footer), encoding="utf-8")

    def count(n):
        return 1 + sum(count(c) for c in n["children"])
    print(f"已生成 {out}（节点 {count(data['root'])}，一级板块 {len(data['root']['children'])}）")


if __name__ == "__main__":
    main()
