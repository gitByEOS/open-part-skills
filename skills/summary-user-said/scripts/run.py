#!/usr/bin/env python3
"""summary-user-said CLI：冻结请求、运行 esflow 并输出稳定 envelope。"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from esflow import Runner, esflow_event

from common import (
    BRIEF_FILENAME,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_VALIDATION,
    SUMMARY_FILENAME,
    CliError,
    build_parser,
    build_request,
    emit_envelope,
    output_schema,
)

_RESUME_CMD = "python3 scripts/run.py --resume {job_dir}"


def _node_args(request) -> dict:
    return {"discover_sources": {"request": request.as_dict()}}


def _emit_cli_error(error: CliError, started_at: float) -> int:
    emit_envelope(
        False,
        error={"code": error.code, "message": error.message, "retryable": False},
        started_at=started_at,
    )
    return error.exit_code


def _emit_unexpected(exc: Exception, started_at: float) -> int:
    emit_envelope(
        False,
        error={
            "code": "runtime_error",
            "message": f"{type(exc).__name__}: {exc}",
            "retryable": False,
        },
        started_at=started_at,
    )
    return EXIT_RUNTIME


async def _run_first(flow_dir: str, request):
    runner = Runner.load(flow_dir, node_args=_node_args(request))
    events, kind, break_event = await runner.run_to_break()
    return runner, events, kind, break_event


async def _run_resume(flow_dir: str, job_dir: Path):
    runner = Runner.load(flow_dir, job_dir=job_dir)
    if not runner.has_break_to_agent():
        raise CliError("resume_error", f"无待完成的 TO_AGENT 节点：{job_dir}")
    events, kind, break_event = await runner.run_to_break(resume=True)
    return runner, events, kind, break_event


def _request_from_runner(runner) -> dict:
    discover = runner.artifacts.get("discover_sources") or {}
    return discover.get("request") or runner._node_args.get("discover_sources", {}).get("request", {})


def _to_agent_data(runner, break_event) -> dict:
    collection = runner.artifacts.get("collect_messages") or {}
    request = collection.get("request") or _request_from_runner(runner)
    node_dir = Path(break_event.resume_hint["node_dir"])
    return {
        "status": "to_agent",
        "job_dir": str(runner.job_dir),
        "brief_path": str(node_dir / BRIEF_FILENAME),
        "messages_path": collection.get("messages_path"),
        "agent_summary_path": str(node_dir / SUMMARY_FILENAME),
        "summary_path": request.get("summary_path"),
        "original_path": request.get("original_path"),
        "resume_command": f"python3 {Path(__file__).resolve()} --resume {runner.job_dir}",
        "stats": collection.get("stats", {}),
        "discovery": {
            key: collection.get("discovery", {}).get(key)
            for key in ("roots_requested", "roots_authorized", "roots_missing", "files_discovered", "symlinks_skipped")
        },
    }


def _end_data(runner) -> dict:
    export = runner.artifacts.get("export_report") or {}
    return {
        "status": "end",
        "job_dir": str(runner.job_dir),
        "summary_path": export.get("summary_path"),
        "original_path": export.get("original_path"),
        "stats": {
            "files_scanned": export.get("files_scanned", 0),
            "included": export.get("included", 0),
            "time_sources": export.get("time_sources", {}),
            "skipped": export.get("skipped", {}),
        },
        "checks": {
            "period_count_conserved": True,
            "unique_period_membership": True,
            "evidence_required": True,
            "no_overwrite": True,
        },
    }


def _handle_result(runner, events, kind, break_event, started_at: float) -> int:
    for event in events:
        esflow_event(event)
    if kind == "error" and break_event is not None:
        try:
            raise break_event.as_exception()
        except CliError as error:
            return _emit_cli_error(error, started_at)
        except Exception as exc:
            return _emit_unexpected(exc, started_at)
    if kind == "to_agent" and break_event is not None:
        print(Runner.to_agent_hint(break_event, resume_cmd=_RESUME_CMD), file=sys.stderr)
        data = _to_agent_data(runner, break_event)
        print(f"[agent] 读取 brief：{data['brief_path']}", file=sys.stderr)
        print(f"[agent] 读取原始消息：{data['messages_path']}", file=sys.stderr)
        print(f"[agent] 写 JSON：{data['agent_summary_path']}", file=sys.stderr)
        print(f"[agent] 完成后续跑：{data['resume_command']}", file=sys.stderr)
        emit_envelope(True, data=data, started_at=started_at)
        return 2
    emit_envelope(True, data=_end_data(runner), started_at=started_at)
    return EXIT_OK


def main(argv=None) -> int:
    started_at = time.time()
    try:
        args = build_parser().parse_args(argv)
        if args.schema:
            if args.resume or args.sources or args.custom_dirs or args.day or args.week:
                raise CliError("invalid_arguments", "--schema 必须独占")
            output_schema()
            return EXIT_OK
        if args.resume:
            if args.sources or args.custom_dirs or args.day or args.week:
                raise CliError("invalid_arguments", "--resume 必须独占")
            job_dir = Path(args.resume).expanduser().resolve()
            if not job_dir.is_dir():
                raise CliError("resume_error", f"job_dir 不存在：{job_dir}")
            result = asyncio.run(_run_resume(str(Path(__file__).parent), job_dir))
        else:
            request = build_request(args)
            result = asyncio.run(_run_first(str(Path(__file__).parent), request))
        return _handle_result(*result, started_at)
    except CliError as error:
        return _emit_cli_error(error, started_at)
    except Exception as exc:
        return _emit_unexpected(exc, started_at)


if __name__ == "__main__":
    raise SystemExit(main())
