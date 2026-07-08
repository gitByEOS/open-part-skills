"""collect_commits 节点:跑 git log 抓 commits,结构化为 JSON。

支持三种 scope:
- since..until (如 2026-05-01..2026-05-07) → --since/--until
- branch1..branch2 → 直接传给 git log
- 单分支 → 该分支 HEAD 全部 commit,但默认限制 --max-count 防爆

排除 merge commit。每条 commit 含 hash/author/email/time/subject。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log, run_git


def _parse_scope(scope: str) -> dict:
    """把 scope 字符串解析成 git log 参数。"""
    if ".." in scope:
        # 时间范围 vs 分支范围的启发式:含 - 且像日期 → 时间;否则按分支范围
        left, right = scope.split("..", 1)
        if _looks_like_date(left) and _looks_like_date(right):
            return {"since": left, "until": right}
        return {"revision_range": scope}
    return {"branch": scope}


def _looks_like_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _build_log_args(parsed: dict, max_count: int) -> list[str]:
    args = ["log", "--no-merges", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso-strict"]
    if max_count > 0:
        args.append(f"--max-count={max_count}")
    if "since" in parsed:
        args.extend([f"--since={parsed['since']}", f"--until={parsed['until']}"])
    elif "revision_range" in parsed:
        args.append(parsed["revision_range"])
    elif "branch" in parsed:
        args.append(parsed["branch"])
    return args


class CollectCommits(Node):
    id = "collect_commits"
    title = "抓取 git commits"

    def run(self, ctx) -> dict:
        plan = ctx.get("resolve")
        repo = Path(plan["repo"])
        scope = plan["scope"]
        config = self.kwargs or {}
        max_count = int(config.get("max_count", 0))

        parsed = _parse_scope(scope)
        args = _build_log_args(parsed, max_count)
        log(f"[collect] git {' '.join(args)} (cwd={repo})")
        stdout = run_git(args, cwd=repo)

        commits = []
        for line in stdout.splitlines():
            parts = line.split("|", 4)
            if len(parts) != 5:
                continue
            commit_hash, author, email, time, subject = parts
            commits.append({
                "hash": commit_hash,
                "author": author,
                "email": email,
                "time": time,
                "subject": subject,
            })

        if not commits:
            raise CliError("validation_error", f"范围内无 commit:{scope}", EXIT_VALIDATION)

        commits_path = self.output_dir / "commits.json"
        commits_path.write_text(json.dumps(commits, ensure_ascii=False, indent=2), encoding="utf-8")

        log(f"[collect] {len(commits)} commits -> {commits_path}")
        return {
            "commits_path": str(commits_path),
            "count": len(commits),
            "scope_kind": next(iter(parsed)),
        }
