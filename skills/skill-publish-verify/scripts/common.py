"""skill-publish-verify 协议层:CliError、错误码、日志、输出契约、文件名常量。

只放跨节点/run.py 共享的协议级定义,业务逻辑住在各节点。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
# 0 ok / 1 runtime / 2 to_agent / 3 validation
EXIT_OK, EXIT_RUNTIME, EXIT_TO_AGENT, EXIT_VALIDATION = 0, 1, 2, 3

DEFAULT_WORK_ROOT = Path("/tmp/skill-publish-verify")

# work_dir 内的固定文件名,节点与 run.py 共用
RUN_RECORD_FILE = "run_record.json"
REPORT_FILE = "skill_verify_report.md"
CASE_FILE = "_case.json"
AGENT_RUN_BRIEF = "_agent_run_brief.json"
AGENT_REPORT_BRIEF = "_agent_report_brief.json"
VERIFY_FACTS_FILE = "verify_facts.json"
INSTALL_DEPS_LOG = "install_deps.log"
PREFLIGHT_NODE = "preflight_target"


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


# —— 输出契约 ——

def schema():
    return {
        "ok": "boolean",
        "data": {
            "work_dir": "string path",
            "report_path": "string path",
            "artifacts": "array,清理后仍存在的产物绝对路径",
            "verify": "object, 摘要(exit_code/envelope_ok/artifact_count),全量事实在清理前已写 verify_facts.json(默认清理删除)",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "2": "to_agent", "3": "validation"},
    }


def output_schema():
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
