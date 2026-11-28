#!/usr/bin/env python3
"""把 lesson.js 内联进讲题模板，输出单文件讲解页。"""
import argparse
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_ROOT / "assets" / "template.html"
MARKER = "/* __LESSON_DATA__ */"
SEQ_WORDS = ("然后", "最后", "首先", "其次", "接着", "随后", "最终", "下一步", "最先")


def seq_word_in(text):
    """原理卡不能带顺序词，否则原理巩固会泄题。优先不算。"""
    cleaned = text.replace("优先", "")
    if "先" in cleaned:
        return "先"
    return next((word for word in SEQ_WORDS if word in cleaned), None)


def theorems_of(data):
    return re.findall(r"theorem:\s*'([^']*)'", data) + re.findall(
        r'theorem:\s*"([^"]*)"', data
    )


def main():
    parser = argparse.ArgumentParser(description="lesson.js → 给孩子讲题的单文件页")
    parser.add_argument("lesson", help="含 const LESSON 的 JS 文件")
    parser.add_argument("-o", "--output", help="输出 HTML 路径")
    args = parser.parse_args()

    lesson_path = Path(args.lesson).expanduser().resolve()
    if not lesson_path.is_file():
        sys.exit(f"错误：找不到 lesson 文件：{lesson_path}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if MARKER not in template:
        sys.exit(f"错误：模板缺少注入点 {MARKER}")

    data = lesson_path.read_text(encoding="utf-8")
    if "const LESSON" not in data:
        sys.exit("错误：lesson 文件必须含 const LESSON")
    if re.search(r"</script", data, re.I):
        sys.exit("错误：lesson 不能含 </script>，会撑破模板")
    for theorem in theorems_of(data):
        word = seq_word_in(theorem)
        if word:
            sys.exit(f"错误：原理卡不能出现顺序词「{word}」：{theorem}")
    if re.search(r"\binfinite\b", data, re.I):
        sys.exit("错误：到位后不要循环动画，待机呼吸由模板提供")
    if len(re.findall(r"\bstem\s*:", data)) < 2:
        sys.exit("错误：需要原题和一道变式，至少两个 stem")

    output = Path(args.output).expanduser().resolve() if args.output else lesson_path.with_suffix(".html")
    if output == TEMPLATE_PATH:
        sys.exit("错误：不能覆盖模板")
    html = template.replace(MARKER, data, 1)
    for tab in ("原题讲解", "触类旁通", "原理巩固"):
        if tab not in html:
            sys.exit(f"错误：产物缺少标签「{tab}」")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"已写入 {output}", flush=True)


if __name__ == "__main__":
    main()
