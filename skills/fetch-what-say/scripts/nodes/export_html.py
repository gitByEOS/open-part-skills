"""export_html 节点:生成 viewer.html 并弹出。

从 ctx 拿:
- transcribe.txt_path:transcript.txt 路径,其 parent 即业务 work_dir
- agent_summary.output_dir:Agent 写 summary.txt 的目录(= work_dir,agent_summary.accept 已设)

Agent 直接写 work_dir/summary.txt,本节点无需搬运,generate_viewer 直接读 work_dir。
HTML 渲染逻辑也放在本模块(--view 由 run.py 直接调 generate_viewer,不进 flow)。
"""

from __future__ import annotations

import re
import subprocess
import sys
import webbrowser
from html import escape
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION


CIRCLE_NUMBER_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #fafafa;
            --surface: #f5f5f5;
            --surface-soft: #f2f3f5;
            --reader-bg: #fffefd;
            --reader-border: #e6dfd5;
            --text: #1a1a1a;
            --muted: #666;
            --accent: #0066cc;
            --border: #e0e0e0;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #1a1a1a;
                --surface: #252525;
                --surface-soft: #222427;
                --reader-bg: #202020;
                --reader-border: #38352f;
                --text: #e8e8e8;
                --muted: #999;
                --accent: #4d9fff;
                --border: #333;
            }}
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            line-height: 1.8;
            padding: 2rem 1rem;
        }}
        .container {{
            max-width: 760px;
            margin: 0 auto;
        }}
        .header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        h1 {{
            margin: 0 0 0.5rem;
            font-size: 1.5rem;
            line-height: 1.35;
            font-weight: 600;
        }}
        .meta {{
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .tabs {{
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }}
        .tab {{
            border: none;
            background: var(--surface);
            color: var(--muted);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
        }}
        .tab.active {{
            background: var(--accent);
            color: white;
        }}
        .content {{
            background: var(--surface);
            border-radius: 12px;
            padding: 2rem;
        }}
        .panel {{
            display: none;
        }}
        .panel.active {{
            display: block;
        }}
        .tree-view {{
            font-family: Menlo, Monaco, "Cascadia Mono", "Courier New", monospace;
            font-size: 0.9375rem;
            line-height: 1.3;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            margin: 0;
            color: var(--text);
        }}
        .tree-title,
        .section-title {{
            font-weight: 700;
        }}
        .tree-title {{
            font-size: 1.05rem;
        }}
        .has-index {{
            color: var(--accent);
            font-weight: 700;
        }}
        .transcript {{
            max-width: 760px;
            margin: 0 auto;
            padding: 1rem 1.1rem;
            border: 1px solid var(--reader-border);
            border-radius: 10px;
            background: var(--reader-bg);
            font-size: 1rem;
            line-height: 1.95;
            letter-spacing: 0.01em;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            color: var(--text);
            font-family: inherit;
        }}
        .empty-state {{
            padding: 3rem 1rem;
            text-align: center;
            color: var(--muted);
        }}
        @media (max-width: 640px) {{
            body {{
                padding: 1rem 0.75rem;
            }}
            .content {{
                padding: 1.25rem;
            }}
            .tree-view {{
                font-size: 0.875rem;
            }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <header class="header">
            <h1>{title}</h1>
            <div class="meta">{meta}</div>
        </header>
        <nav class="tabs">
            {tabs}
        </nav>
        <section class="content">
            {panels}
        </section>
    </main>
    <script>
        function switchTab(name) {{
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            document.getElementById('panel-' + name).classList.add('active');
        }}
    </script>
</body>
</html>
'''


def _format_file_size(path):
    size = path.stat().st_size
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / 1024 / 1024:.1f}MB"


def _is_section_title(line, index):
    if index == 0 or CIRCLE_NUMBER_RE.search(line):
        return False
    return "：" in line and not line.lstrip().startswith(("│", "├", "└"))


def _render_tree(text):
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return '<div class="empty-state">暂无摘要</div>'

    rendered = []
    for index, line in enumerate(lines):
        classes = []
        if index == 0:
            classes.append("tree-title")
        if _is_section_title(line, index):
            classes.append("section-title")
        index_match = CIRCLE_NUMBER_RE.search(line)
        if index_match:
            prefix = escape(line[:index_match.start()], quote=False)
            indexed = escape(line[index_match.start():], quote=False)
            escaped = f'{prefix}<span class="has-index">{indexed}</span>'
        else:
            escaped = escape(line, quote=False)
        if classes:
            rendered.append(f'<span class="{" ".join(classes)}">{escaped}</span>')
        else:
            rendered.append(escaped)
    return "\n".join(rendered)


def _render_transcript(text):
    lines = [
        re.sub(r"\s+", " ", raw_line).strip()
        for raw_line in text.splitlines()
        if raw_line.strip()
    ]
    if not lines:
        return '<div class="empty-state">暂无全文</div>'
    return escape("\n".join(lines), quote=False)


def _build_viewer(work_dir):
    work_dir = Path(work_dir).expanduser()
    summary_path = work_dir / "summary.txt"
    transcript_path = work_dir / "transcript.txt"

    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else None
    transcript_text = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else None

    if summary_text and summary_text.strip():
        first_line = summary_text.strip().splitlines()[0]
        title = first_line[:64] + ("..." if len(first_line) > 64 else "")
    else:
        title = work_dir.name

    tabs = []
    panels = []
    active_set = False
    if summary_text:
        tabs.append('<button id="tab-summary" class="tab active" onclick="switchTab(\'summary\')">摘要</button>')
        panels.append(f'<div id="panel-summary" class="panel active"><pre class="tree-view">{_render_tree(summary_text)}</pre></div>')
        active_set = True
    if transcript_text:
        active_class = "active" if not active_set else ""
        tabs.append(f'<button id="tab-transcript" class="tab {active_class}" onclick="switchTab(\'transcript\')">全文</button>')
        panels.append(f'<div id="panel-transcript" class="panel {active_class}"><pre class="transcript">{_render_transcript(transcript_text)}</pre></div>')

    if not panels:
        panels.append('<div class="empty-state">未找到 summary.txt 或 transcript.txt</div>')

    meta_parts = []
    if summary_path.exists():
        meta_parts.append(f"摘要 {_format_file_size(summary_path)}")
    if transcript_path.exists():
        meta_parts.append(f"全文 {_format_file_size(transcript_path)}")
    meta = " · ".join(meta_parts) if meta_parts else str(work_dir)

    return HTML_TEMPLATE.format(
        title=escape(title, quote=False),
        meta=escape(meta, quote=False),
        tabs="\n".join(tabs),
        panels="\n".join(panels),
    )


def generate_viewer(work_dir):
    """生成 viewer.html 并打开浏览器。run.py --view 与 export_html 节点共用此入口。"""
    work_dir = Path(work_dir).expanduser()
    if not work_dir.exists():
        raise CliError("validation_error", f"目录不存在：{work_dir}", EXIT_VALIDATION)
    html_path = work_dir / "viewer.html"
    html_path.write_text(_build_viewer(work_dir), encoding="utf-8")
    if sys.platform == "darwin":
        subprocess.run(["open", str(html_path)], check=False)
    else:
        webbrowser.open(html_path.resolve().as_uri())
    print(f"viewer: {html_path}")


class ExportHtml(Node):
    id = "export_html"
    title = "生成 viewer"

    def accept(self, ctx) -> bool:
        """transcribe 被跳过时(--no-transcribe),本节点一并跳过。"""
        return ctx.get("transcribe") is not None

    def run(self, ctx) -> dict:
        transcribe = ctx.get("transcribe")
        work_dir = Path(transcribe["txt_path"]).parent

        # agent_summary 已把 output_dir 设为 work_dir,Agent 直接写 work_dir/summary.txt
        # 无需 copy2 搬运,generate_viewer 直接读 work_dir/summary.txt
        generate_viewer(work_dir)
        return {"viewer_path": str(work_dir / "viewer.html")}

    def deliver(self, artifact) -> bool:
        return Path(artifact["viewer_path"]).exists()
