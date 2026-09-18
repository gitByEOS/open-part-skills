"""meet-digest 协议：退出码、envelope、文件名。"""
from __future__ import annotations

import json
import sys

SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "meet-digest"
EXIT_OK, EXIT_RUNTIME, EXIT_TO_AGENT, EXIT_VALIDATION = 0, 1, 2, 3

SRT_NAME = "srt.md"
WHOLE_NAME = "transcript-whole.txt"
PROGRESS_NAME = "_transcribe_progress.json"
AUDIO_16K_NAME = "audio_16k.wav"
CHUNK_DIR_NAME = "_chunks_16k"
MEET_DRAFT = "meet.md"
BRIEF_FILENAME = "_agent_digest_brief.json"

DIGEST_HINT = (
    "[样式] 只根据转写原文写会议总结，禁止编造。"
    "章节名与顺序固定：会议主题、讨论问题、话题一…、待办与落地、风险与未决项。"
    "每个话题含问题与痛点 / 造成原因 / 方案与建议。"
    "读 brief 里的 whole_path 到最后一句，方案和待办必须能在原文搜到。"
    "写到本节点目录的 meet.md，不要写进 .esflow。"
)


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


def schema():
    return {
        "ok": "boolean",
        "data": {
            "job_dir": "string path, esflow job 目录",
            "wav": "string path",
            "srt": "string path, transcribe/srt.md",
            "whole": "string path, transcribe/transcript-whole.txt",
            "meet_path": "string path, export_meet/meet-YYYY-MM-DD.md (end)",
            "brief_path": f"string path, agent_digest/{BRIEF_FILENAME} (to_agent)",
            "draft_path": f"string path, agent_digest/{MEET_DRAFT} 写入目标 (to_agent)",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "2": "to_agent", "3": "validation"},
    }


def output_schema():
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
