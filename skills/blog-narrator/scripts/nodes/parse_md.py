"""parse_md 节点:读 Markdown → strip frontmatter/分割线 → HTML + 抽标题/段文本。

两条路径共用入口:preview 取 title+body_html,TTS 取 texts。
narrator_core.BASE_DIR 在此设置(图片相对路径基准)。
"""

from __future__ import annotations

import os
from pathlib import Path

from esflow import Node

import narrator_core
from common import CliError, EXIT_VALIDATION, log


class ParseMd(Node):
    id = "parse_md"
    title = "解析 Markdown"

    def accept(self, ctx) -> bool:
        return True

    def run(self, ctx) -> dict:
        kw = self.kwargs or {}
        input_path = Path(kw["input"]).expanduser().resolve()
        if not input_path.is_file():
            raise CliError("input_not_found", f"文件不存在:{input_path}", EXIT_VALIDATION)

        narrator_core.BASE_DIR = os.environ.get("BLOG_NARRATOR_IMAGE_BASE", os.getcwd())

        md_text = input_path.read_text(encoding="utf-8")
        content_md = narrator_core.strip_horizontal_rules(narrator_core.strip_frontmatter(md_text))
        title = narrator_core.extract_title(content_md, input_path.name)
        body_html = narrator_core.embed_images(narrator_core.md_to_html(content_md))
        texts = narrator_core.extract_slide_texts(body_html)

        log(f"[parse_md] {input_path.name} | 标题={title} | 段数={len(texts)}")
        return {
            "input_path": str(input_path),
            "input_stem": input_path.stem,
            "title": title,
            "body_html": body_html,
            "texts": texts,
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("body_html") is not None)
