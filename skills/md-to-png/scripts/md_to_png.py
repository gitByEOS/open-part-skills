#!/usr/bin/env python3
"""把 Markdown 文件渲染成 VitePress 风格 HTML，再调用 html-cut 截图为 PNG。

用法:
  python3 scripts/md_to_png.py path/to/skill.md /tmp/out.png
  python3 scripts/md_to_png.py SKILL.md --width 740 --scale 2 --color-scheme light
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


HTML_CUT_SCRIPT = Path(__file__).resolve().parents[2] / "html-cut" / "scripts" / "capture.py"


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = _escape_html(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def md_to_html(md_text: str) -> str:
    """极简 Markdown 转 HTML，保留常见语法。"""
    lines = md_text.split("\n")
    out: list[str] = []
    in_code_block = False
    in_list = False
    in_table = False
    table_has_header = False

    for line in lines:
        stripped = line.strip()

        # fenced code block
        if stripped.startswith("```"):
            if in_code_block:
                out.append("</code></pre>")
                in_code_block = False
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if in_table:
                    out.append("</tbody></table>")
                    in_table = False
                    table_has_header = False
                lang = stripped[3:].strip()
                out.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue

        if in_code_block:
            out.append(_escape_html(line))
            continue

        # table
        if re.match(r"^\|.*\|$", stripped) or re.match(r"^\|-+", stripped):
            if in_list:
                out.append("</ul>")
                in_list = False
            if not in_table:
                in_table = True
                table_has_header = False
                out.append("<table>")
            if re.match(r"^\|?[\s:-]+\|", stripped) and "=" not in stripped and "---" in stripped:
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if any("---" in c for c in cells):
                continue
            if not table_has_header:
                cells_html = "".join(f"<th>{_inline(c)}</th>" for c in cells)
                out.append(f"<thead><tr>{cells_html}</tr></thead><tbody>")
                table_has_header = True
            else:
                cells_html = "".join(f"<td>{_inline(c)}</td>" for c in cells)
                out.append(f"<tr>{cells_html}</tr>")
            continue
        elif in_table:
            out.append("</tbody></table>")
            in_table = False
            table_has_header = False

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        # empty line
        if stripped == "":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue

        # unordered list
        if stripped.startswith("- "):
            if not in_list:
                in_list = True
                out.append("<ul>")
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        elif in_list:
            out.append("</ul>")
            in_list = False

        # paragraph
        has_br = line.endswith("    ") or line.endswith("  ")
        p_content = _inline(stripped)
        if has_br:
            p_content += "<br>"
        out.append(f"<p>{p_content}</p>")

    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</tbody></table>")

    return "\n".join(out)


def build_html(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, 'Helvetica Neue', Arial, sans-serif;
  color: #3c3c43;
  max-width: 740px;
  margin: 0 auto;
  padding: 40px 24px 80px;
  line-height: 1.7;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  background: #fff;
}}
h1 {{ font-size: 2.2em; font-weight: 600; margin-top: 0; margin-bottom: 12px; letter-spacing: -0.5px; color: #213547; }}
h2 {{ font-size: 1.55em; font-weight: 600; margin-top: 48px; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid #e2e2e3; color: #213547; }}
h3 {{ font-size: 1.3em; font-weight: 600; margin-top: 32px; margin-bottom: 12px; color: #213547; }}
h4 {{ font-size: 1.15em; font-weight: 600; margin-top: 24px; margin-bottom: 8px; color: #213547; }}
p {{ margin: 0 0 16px; }}
p:last-child {{ margin-bottom: 0; }}
ul, ol {{ padding-left: 24px; margin: 0 0 16px; }}
li {{ margin-bottom: 4px; }}
a {{ color: #3eaf7c; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{
  font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.875em;
  background: #f1f1f2;
  padding: 2px 6px;
  border-radius: 4px;
  color: #3e63dd;
}}
pre {{
  background: #f6f6f7;
  border: 1px solid #e2e2e3;
  border-radius: 8px;
  padding: 16px 20px;
  overflow-x: auto;
  margin: 0 0 16px;
  font-size: 0.85em;
  line-height: 1.6;
}}
pre code {{
  background: none;
  padding: 0;
  border-radius: 0;
  color: #3c3c43;
  font-size: inherit;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 20px;
  font-size: 0.95em;
}}
th, td {{
  border: 1px solid #e2e2e3;
  padding: 8px 14px;
  text-align: left;
}}
th {{ background: #f6f6f7; font-weight: 600; }}
blockquote {{
  border-left: 4px solid #3eaf7c;
  margin: 0 0 16px;
  padding: 8px 16px;
  background: #f6f6f7;
  border-radius: 0 4px 4px 0;
  color: #5a5a5a;
}}
strong {{ font-weight: 600; color: #213547; }}
hr {{ border: none; border-top: 1px solid #e2e2e3; margin: 32px 0; }}
@media (prefers-color-scheme: dark) {{
  body {{ color: #e3e3e3; background: #1e1e20; }}
  h1, h2, h3, h4 {{ color: #eaeaea; }}
  h2 {{ border-bottom-color: #3a3a3a; }}
  code {{ background: #2a2a2a; color: #7eb7ff; }}
  pre {{ background: #252526; border-color: #3a3a3a; }}
  pre code {{ color: #e3e3e3; }}
  th {{ background: #2a2a2a; }}
  th, td {{ border-color: #3a3a3a; }}
  blockquote {{ background: #252526; border-left-color: #3eaf7c; color: #b0b0b0; }}
  strong {{ color: #eaeaea; }}
  hr {{ border-top-color: #3a3a3a; }}
}}
</style>
</head>
<body>

{body_html}

</body>
</html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Markdown → HTML → PNG")
    parser.add_argument("md", type=Path, help="Markdown 文件路径")
    parser.add_argument("output", nargs="?", type=Path, help="PNG 输出路径，默认临时目录")
    parser.add_argument("--title", default="", help="HTML 标题，默认取 md 首个标题")
    parser.add_argument("--width", type=int, default=740, help="视口宽度，默认 740")
    parser.add_argument("--scale", type=int, default=2, help="设备像素比，默认 2")
    parser.add_argument("--color-scheme", choices=("dark", "light"), default="light")
    parser.add_argument("--wait", type=int, default=500, metavar="MS", help="加载后等待毫秒，默认 500")
    parser.add_argument("--height", type=int, default=900, help="视口高度，默认 900")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.md.is_file():
        print(f"文件不存在: {args.md}", file=sys.stderr)
        return 1
    if not HTML_CUT_SCRIPT.is_file():
        print(f"找不到 html-cut 脚本: {HTML_CUT_SCRIPT}", file=sys.stderr)
        return 2

    md_text = args.md.read_text(encoding="utf-8")
    # 去除 YAML frontmatter
    content = re.sub(r"^---\n.*?\n---\n?", "", md_text, count=1, flags=re.DOTALL)
    if content == md_text:
        content = md_text

    body = md_to_html(content)
    title = args.title
    if not title:
        first_line = content.split("\n")[0].lstrip("#").strip()
        title = first_line or args.md.stem

    html = build_html(title, body)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(html)
        html_path = Path(tmp.name)

    output = args.output or Path(tempfile.gettempdir()) / f"{args.md.stem}.png"
    cmd = [
        sys.executable, str(HTML_CUT_SCRIPT),
        f"file://{html_path}", str(output),
        "--width", str(args.width),
        "--height", str(args.height),
        "--scale", str(args.scale),
        "--color-scheme", args.color_scheme,
        "--wait", str(args.wait),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    html_path.unlink(missing_ok=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
