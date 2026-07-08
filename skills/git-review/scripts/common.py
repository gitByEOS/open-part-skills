"""git-review 共用工具:错误码、日志、git 调用、schema。

不依赖 esflow,节点与 run.py 共用。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys


SCHEMA_VERSION = "1.2.0"
# 0 ok / 1 runtime / 2 to_agent / 3 validation / 4 auth
EXIT_OK, EXIT_RUNTIME, EXIT_TO_AGENT, EXIT_VALIDATION, EXIT_AUTH = 0, 1, 2, 3, 4

RISK_ORDER = ["P0", "P1", "P2", "P3", "P4", "P5"]
RISK_RANK = {risk: index for index, risk in enumerate(RISK_ORDER)}

# review.json 契约:6 必填 + 3 可选,三处声明(SKILL.md / vigil.md / deliver)以此为准
REVIEW_REQUIRED_FIELDS = {"hash", "author", "risk_level", "risk_summary", "files", "fix_suggestion"}
REVIEW_OPTIONAL_FIELDS = {"time", "subject", "cause"}
RISK_LEVELS = set(RISK_ORDER)


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


def safe_id(value):
    return re.sub(r"\W+", "_", value).strip("_")[-80:] or "review"


def run_git(args, cwd, *, want_stderr=False):
    """统一 git 调用,失败抛 CliError。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if want_stderr else sys.stderr,
        text=True,
    )
    if result.returncode != 0:
        raise CliError("git_error", f"git {' '.join(args)} 失败,exit={result.returncode}", EXIT_RUNTIME, True)
    return result.stdout if not want_stderr else result


def validate_review_item(item):
    """校验单条 review 记录,返回错误描述列表(空列表表示通过)。"""
    errors = []
    if not isinstance(item, dict):
        return ["记录必须是对象"]
    missing = REVIEW_REQUIRED_FIELDS - item.keys()
    if missing:
        errors.append(f"缺字段:{','.join(sorted(missing))}")
    level = item.get("risk_level")
    if level is not None and level not in RISK_LEVELS:
        errors.append(f"risk_level 非法:{level},必须 {','.join(RISK_ORDER)}")
    files = item.get("files")
    if files is not None and (not isinstance(files, list) or not all(isinstance(f, str) for f in files)):
        errors.append("files 必须是字符串数组,每个元素格式 path:起始行-结束行")
    for str_field in ("hash", "author", "risk_summary", "fix_suggestion"):
        value = item.get(str_field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{str_field} 必须是字符串")
    return errors


def validate_review_json(data):
    """校验整个 review.json 结构,返回 (ok, errors)。"""
    if not isinstance(data, dict):
        return False, ["review.json 顶层必须是对象"]
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        return False, ["reviews 必须是数组"]
    if not reviews:
        return False, ["reviews 不能为空"]
    all_errors = []
    for index, item in enumerate(reviews):
        errors = validate_review_item(item)
        if errors:
            all_errors.append(f"reviews[{index}]: {'; '.join(errors)}")
    return (not all_errors), all_errors


# —— 输出契约 ——

def schema():
    return {
        "ok": "boolean",
        "data": {
            "commits": "string path, commits.json 清单",
            "review_path": "string path, review.json 写入路径 (TO_AGENT 退出时给)",
            "vigil_md": "string path, assets/vigil.md (TO_AGENT 退出时给)",
            "aggregate": "string path, aggregate.json",
            "report": "string path, security_report.html",
            "process_md": "string path, process.md (人读)",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "2": "to_agent", "3": "validation", "4": "auth"},
    }


def output_schema():
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
