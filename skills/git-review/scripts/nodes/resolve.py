"""resolve 节点:解析时间范围/分支范围与仓库,产出 plan。

CLI 参数由 Runner.load(node_args=...) 注入到 self.kwargs。
支持三种范围:
- since..until 时间范围 (如 2026-05-01..2026-05-07)
- branch1..branch2 分支范围
- 单分支 (该分支全部 commit)
"""

from __future__ import annotations

from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log, safe_id


class Resolve(Node):
    id = "resolve"
    title = "解析范围与仓库"

    def run(self, ctx) -> dict:
        args = self.kwargs or {}
        repo = Path(args.get("repo") or ".").expanduser().resolve()
        if not (repo / ".git").exists():
            raise CliError("validation_error", f"不是 git 仓库:{repo}", EXIT_VALIDATION)
        scope = args.get("scope")
        if not scope:
            raise CliError("validation_error", "缺少审查范围,见 --scope", EXIT_VALIDATION)

        plan = {
            "repo": str(repo),
            "scope": scope,
            "scope_id": safe_id(scope),
        }
        log(f"[resolve] repo={repo} scope={scope} scope_id={plan['scope_id']}")
        return plan
