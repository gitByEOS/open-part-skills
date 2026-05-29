#!/usr/bin/env python3
"""
将 Markdown 导出为无预录音的逐行披露 HTML（体积小，适合快速预览）。
用法: python3 {skill}/scripts/export_small_size.py <input.md> <output.html> [--rate 1.15] [--open]
"""
from pathlib import Path
import os
import sys
import webbrowser

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import narrator_core  # noqa: E402

def parse_option(argv: list[str], name: str, default: str) -> str:
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        print(f"{name} 缺少参数")
        sys.exit(1)
    return argv[index + 1]

def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path

def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python3 {skill}/scripts/export_small_size.py <input.md> <output.html> [--rate 1.15] [--open]")
        sys.exit(1)

    input_file = resolve_path(sys.argv[1])
    output_file = resolve_path(sys.argv[2])
    should_open = "--open" in sys.argv
    try:
        rate = float(parse_option(sys.argv, "--rate", "1.15"))
    except ValueError:
        print("--rate 需要指定数字")
        sys.exit(1)

    if not input_file.is_file():
        print(f"文件不存在: {input_file}")
        sys.exit(1)

    narrator_core.BASE_DIR = os.environ.get("BLOG_NARRATOR_IMAGE_BASE", os.getcwd())

    md_text = input_file.read_text(encoding="utf-8")
    content_md = narrator_core.strip_horizontal_rules(narrator_core.strip_frontmatter(md_text))
    title = narrator_core.extract_title(content_md, input_file.name)
    body_html = narrator_core.embed_images(narrator_core.md_to_html(content_md))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(narrator_core.build_stage_html(title, body_html, rate=rate), encoding="utf-8")

    print(f"已导出: {output_file} ({output_file.stat().st_size} bytes)")
    if should_open:
        webbrowser.open(output_file.resolve().as_uri())

if __name__ == "__main__":
    main()
