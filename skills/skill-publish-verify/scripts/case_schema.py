"""用例契约校验:JSON 用例,只含 skill_path + demand。

不描述怎么用 skill(命令由 agent 读 SKILL.md 自己构造),不描述期望产物格式
(验证需求由人读 report 判断,不预设 schema)。极简输入,最大化通用性。
"""

from __future__ import annotations

import json
from pathlib import Path

from common import CliError, EXIT_VALIDATION


def parse_case(path):
    """读 JSON 用例,校验结构,返回 {skill_path, demand}。"""
    p = Path(path).expanduser()
    if not p.is_file():
        raise CliError("case_error", f"用例文件不存在:{p}", EXIT_VALIDATION)
    try:
        case = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("case_error", f"用例 JSON 解析失败:{exc}", EXIT_VALIDATION) from exc

    if not isinstance(case, dict):
        raise CliError("case_error", "用例必须是 JSON 对象", EXIT_VALIDATION)
    for key in ("skill_path", "demand"):
        if key not in case:
            raise CliError("case_error", f"用例缺少字段:{key}", EXIT_VALIDATION)
    if not isinstance(case["demand"], str) or not case["demand"].strip():
        raise CliError("case_error", "demand 必须是非空字符串", EXIT_VALIDATION)

    skill_path = Path(case["skill_path"]).expanduser()
    if not skill_path.is_dir():
        raise CliError("case_error", f"skill_path 不是目录:{skill_path}", EXIT_VALIDATION)
    if not (skill_path / "SKILL.md").is_file():
        raise CliError("case_error", f"skill_path 下缺少 SKILL.md:{skill_path}", EXIT_VALIDATION)

    case["skill_path"] = str(skill_path)
    return case
