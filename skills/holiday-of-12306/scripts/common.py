"""holiday-of-12306 协议层:CliError、错误码、日志、网络常量、输出契约。

只放跨节点共享的协议级定义,业务逻辑(车站匹配/起售时间/节假日/HTML)一律住在各节点。
"""

from __future__ import annotations

import json
import sys


SCHEMA_VERSION = "1.0.0"
# 0 ok / 1 runtime / 3 validation
EXIT_OK, EXIT_RUNTIME, EXIT_VALIDATION = 0, 1, 3

# 网络请求统一超时(车站表/起售时间/节假日库升级共用)
REQUEST_TIMEOUT = 15


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
            "html_path": "string path",
            "departure": "string",
            "return": "string|null",
            "year": "integer",
            "festivals": "array",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "3": "validation"},
    }


def output_schema():
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
