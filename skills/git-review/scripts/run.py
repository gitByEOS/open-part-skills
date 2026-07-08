#!/usr/bin/env python3
"""git-review 入口:argparse + pass_check 预检 + 启动 esflow runner。

直接跑:python3 scripts/run.py --repo <path> --scope <range>
跑到达 agent_review 节点退出(exit 2),Agent 写 review.json 后:
python3 scripts/run.py --resume <job_dir>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from esflow import (
    BreakKind,
    CheckResult,
    FlowCheckError,
    JobEvent,
    Runner,
    esflow_event,
    pass_check,
)

from common import (
    CliError,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_VALIDATION,
    SCHEMA_VERSION,
    output_schema,
)


# TO_AGENT 续跑命令模板,{job_dir} 由 Runner.to_agent_hint 填充
_RESUME_CMD = "python3 scripts/run.py --resume {job_dir}"


# —— 预检 ——

def _check_scope(value):
    return None if value else "缺少 --scope"


def _check_git():
    if shutil.which("git"):
        return None
    return CheckResult(reason="未安装 git", fix="brew install git / sudo apt install git")


def _check_repo(value):
    if not value:
        return None
    if (Path(value).expanduser() / ".git").exists():
        return None
    return CheckResult(reason=f"不是 git 仓库:{value}", fix="确认路径或先 git init")


# —— 参数 ——

def build_parser():
    parser = argparse.ArgumentParser(description="Git 提交安全审查:抓 commits → Agent 审 → 聚合 → HTML 报告")
    parser.add_argument("--repo", default=".", help="被审查的 git 仓库路径,默认当前目录")
    parser.add_argument("--scope", help="审查范围:since..until 日期 / branch1..branch2 / 单分支")
    parser.add_argument("--out", default=None, help="esflow output_root,默认 /tmp/esflow/outputs")
    parser.add_argument("--resume", metavar="JOB_DIR", help="从 job_dir 续跑 TO_AGENT 节点")
    parser.add_argument("--job-dir", metavar="DIR", help="指定 esflow job 目录")
    parser.add_argument("--max-count", type=int, default=0, help="单分支模式下最多抓多少 commit,0 不限")
    parser.add_argument("--no-open", action="store_true", help="生成 HTML 后不弹浏览器,给 CI/无头环境")
    parser.add_argument("--dry-run", action="store_true", help="只跑 resolve 产出 plan")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _build_node_args(args) -> dict[str, dict]:
    return {
        "resolve": {
            "repo": args.repo,
            "scope": args.scope,
        },
        "collect_commits": {
            "max_count": args.max_count,
        },
        "export_html": {
            "open_browser": not args.no_open,
        },
    }


# —— 输出 ——

def _emit_envelope(ok, data=None, error=None, started_at=0.0):
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "git-review",
            "elapsed_ms": int((time.time() - started_at) * 1000),
        },
    }
    print(json.dumps(envelope, ensure_ascii=False))


def _emit_error(error, started_at):
    _emit_envelope(False, error={"code": error.code, "message": error.message, "retryable": error.retryable}, started_at=started_at)
    return error.exit_code


def _emit_unexpected(exc, started_at):
    _emit_envelope(False, error={"code": "unexpected", "message": f"{type(exc).__name__}: {exc}", "retryable": False}, started_at=started_at)
    return EXIT_RUNTIME


# —— flow 执行 ——

async def _run_to_break(runner, only=None, resume=False) -> tuple[BreakKind, JobEvent | None]:
    events, break_kind, break_event = await runner.run_to_break(only=only, resume=resume)
    for event in events:
        esflow_event(event)
    if break_kind == "to_agent" and break_event is not None:
        print(Runner.to_agent_hint(break_event, resume_cmd=_RESUME_CMD), file=sys.stderr)
    return break_kind, break_event


async def _run_flow(flow_dir, output_root, job_dir, args, only=None):
    kwargs = {"job_dir": job_dir, "node_args": _build_node_args(args)}
    if output_root is not None:
        kwargs["output_root"] = output_root
    runner = Runner.load(flow_dir, **kwargs)
    break_kind, break_event = await _run_to_break(runner, only=only)
    return runner, break_kind, break_event


async def _run_resume(flow_dir, job_dir, args):
    runner = Runner.load(
        flow_dir,
        job_dir=job_dir,
        node_args=_build_node_args(args),
    )
    if not runner.has_break_to_agent():
        raise CliError("resume_error", f"无待完成的 TO_AGENT 节点:{job_dir}", EXIT_VALIDATION)
    break_kind, break_event = await _run_to_break(runner, resume=True)
    return runner, break_kind, break_event


def _build_success_data(runner):
    artifacts = runner.artifacts
    collect = artifacts.get("collect_commits")
    aggregate = artifacts.get("aggregate")
    export_html = artifacts.get("export_html")
    data = {}
    if collect:
        data["commits"] = collect.get("commits_path")
    if aggregate:
        data["aggregate"] = aggregate.get("aggregate_path")
        data["process_md"] = aggregate.get("process_path")
    if export_html:
        data["report"] = export_html.get("report_path")
    return data


def _build_to_agent_data(runner):
    """TO_AGENT 退出时输出 envelope data:Agent 接管需要的路径集合。"""
    artifacts = runner.artifacts
    collect = artifacts.get("collect_commits")
    agent_node = runner.runs.get("agent_review")
    data = {
        "vigil_md": str(Path(__file__).parent.parent / "assets" / "vigil.md"),
    }
    if agent_node is not None:
        data["review_path"] = str(agent_node.output_dir / "review.json")
    if collect:
        data["commits"] = collect.get("commits_path")
        data["commits_count"] = collect.get("count")
    return data


def _run_with_envelope(coro_factory, started_at, *, build_data=None):
    try:
        runner, break_kind, break_event = asyncio.run(coro_factory())
    except CliError as error:
        return _emit_error(error, started_at)
    except Exception as exc:
        return _emit_unexpected(exc, started_at)

    if break_kind == "error":
        try:
            raise break_event.as_exception()
        except CliError as error:
            return _emit_error(error, started_at)
        except Exception as exc:
            return _emit_unexpected(exc, started_at)

    exit_code, _ = Runner.to_envelope(break_kind, break_event)
    if break_kind == "end":
        _emit_envelope(True, data=build_data(runner) if build_data else None, started_at=started_at)
    elif break_kind == "to_agent":
        # TO_AGENT 也输出 envelope,Agent 按契约解析 stdout 能拿到 review_path/commits/vigil_md
        _emit_envelope(True, data=_build_to_agent_data(runner), started_at=started_at)
    return exit_code


# —— 主流程 ——

def main():
    started_at = time.time()
    args = build_parser().parse_args()
    flow_dir = str(Path(__file__).parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.resume:
        return _run_with_envelope(
            lambda: _run_resume(flow_dir, args.resume, args),
            started_at, build_data=_build_success_data,
        )

    # 预检
    def check_scope():
        return _check_scope(args.scope)

    def check_repo():
        return _check_repo(args.repo)

    try:
        pass_check(check_scope, _check_git, check_repo)
    except FlowCheckError as exc:
        print(f"预检失败:\n{exc}", file=sys.stderr)
        return EXIT_VALIDATION

    output_root = Path(args.out).expanduser() if args.out else None
    job_dir = Path(args.job_dir) if args.job_dir else None

    if args.dry_run:
        return _run_with_envelope(
            lambda: _run_flow(flow_dir, output_root, job_dir, args, only={"resolve"}),
            started_at, build_data=lambda r: {"dry_run": True, "plan": r.artifacts.get("resolve", {})},
        )

    return _run_with_envelope(
        lambda: _run_flow(flow_dir, output_root, job_dir, args),
        started_at, build_data=_build_success_data,
    )


if __name__ == "__main__":
    raise SystemExit(main())
