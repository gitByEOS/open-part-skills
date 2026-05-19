#!/usr/bin/env python3
"""从交接 HTML 中还原结构化文本。用法: python3 read.py [handoff.html]"""

import json
import re
import sys
from pathlib import Path


DEFAULT_HANDOFF_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'continue.html'


def parse_html(content: str) -> tuple[str, list[dict]]:
    """从 HTML 中提取 SECTION_DATA JSON 和标题"""
    # 提取标题（input 或 h1）
    title_match = re.search(r'<input[^>]*id="mainTitle"[^>]*value="([^"]*)"', content)
    if not title_match:
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else '未知任务'

    # 提取 SECTION_DATA JSON
    data_match = re.search(r'var SECTIONS\s*=\s*(\[.*?\]);', content, re.DOTALL)
    if not data_match:
        return title, []

    sections_data = json.loads(data_match.group(1))
    return title, sections_data


def format_output(title: str, sections: list[dict]) -> str:
    """格式化为可读的结构化文本"""
    lines = [f'# {title}', '']

    for sec in sections:
        lines.append(f'## {sec["title"]}')
        lines.append('')

        for p in sec.get('paragraphs', []):
            lines.append(p)
            lines.append('')

        for item in sec.get('items', []):
            if item['type'] == 'done':
                lines.append(f'- [x] {item["text"]}')
            elif item['type'] == 'todo':
                lines.append(f'- [ ] {item["text"]}')
            else:
                lines.append(f'- {item["text"]}')

        lines.append('')

    return '\n'.join(lines)


def main():
    in_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else DEFAULT_HANDOFF_PATH

    if not in_path.is_file():
        print(f"文件不存在: {in_path}")
        sys.exit(1)

    html_content = in_path.read_text(encoding='utf-8')
    title, sections = parse_html(html_content)

    if not sections:
        print("错误: 未在 HTML 中找到交接内容")
        sys.exit(1)

    output = format_output(title, sections)
    print(output)

    total_items = sum(len(s.get('paragraphs', [])) + len(s.get('items', [])) for s in sections)
    print(f"\n--- 共 {len(sections)} 个区块, {total_items} 条内容 ---", file=sys.stderr)


if __name__ == '__main__':
    main()
