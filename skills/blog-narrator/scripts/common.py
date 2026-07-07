"""blog-narrator 协议层:CliError、错误码、日志、输出契约。

只放跨节点共享的协议级定义,业务逻辑(MD→HTML、分段、TTS、ASR 对齐)一律住在各节点。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
# 0 ok / 1 runtime / 3 validation
EXIT_OK, EXIT_RUNTIME, EXIT_VALIDATION = 0, 1, 3


class CliError(Exception):
    """带稳定错误码的 CLI 异常。"""

    def __init__(self, code, message, exit_code=EXIT_RUNTIME, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable


def log(message):
    print(message, file=sys.stderr, flush=True)


def load_srt_texts(srt_file: Path) -> list[str]:
    """从 srt.md 读各段文本(去掉段号标题与空行标记)。gen/match 共用。"""
    content = srt_file.read_text(encoding="utf-8")
    texts = []
    for part in re.split(r"## \[\d+\]", content)[1:]:
        text_lines = [
            line.strip()
            for line in part.strip().split("\n")
            if line.strip() and not line.startswith("⚪") and not line.startswith("（")
        ]
        texts.append(" ".join(text_lines) if text_lines else "")
    return texts


# —— 输出契约 ——


def schema():
    return {
        "ok": "boolean",
        # preview 模式:{html_path};tts 模式:{html_path, work_dir, segment_count, audio_count}
        "data": "object|null",
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "3": "validation"},
        "modes": {"preview": "轻量预览 HTML,无预录音", "tts": "Edge TTS 分段配音合并 HTML"},
    }


def output_schema():
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
