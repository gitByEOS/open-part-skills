#!/usr/bin/env python3
"""天气面状查询入口。

用法:
    python3 scripts/run.py --query 地点 [--days 天数] [--radius-km 半径] [--out 目录]

示例:
    python3 scripts/run.py --query 北京天安门
    python3 scripts/run.py --query 北京天安门 --days 3 --radius-km 10 --out ./out

跑到 agent_advice(TO_AGENT) exit 2,stdout 为 envelope;stderr 为介入指引与样式约束。
写 advice.md 后:python3 scripts/run.py --resume <job_dir>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request
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
    ADVICE_STYLE_HINT,
    CliError,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_VALIDATION,
    SCHEMA_VERSION,
    analyze_grid_artifact_path,
    output_schema,
)
from weather_domain import ADVICE_FILENAME, DEFAULT_DAYS, DEFAULT_RADIUS_KM

_RESUME_CMD = "python3 scripts/run.py --resume {job_dir}"


def check_python_version() -> CheckResult | None:
    if sys.version_info >= (3, 10):
        return None
    return CheckResult(
        reason=f"需要 Python >= 3.10,当前 {sys.version_info.major}.{sys.version_info.minor}",
        fix="升级 Python 到 3.10+",
    )


def check_network() -> CheckResult | None:
    try:
        request = urllib.request.Request(
            "https://nominatim.openstreetmap.org/search?q=beijing&format=json&limit=1",
            headers={"User-Agent": "esflow-weather-skill/1.0"},
        )
        urllib.request.urlopen(request, timeout=5).close()
        return None
    except Exception as exc:
        return CheckResult(
            reason=f"无法连接地点编码服务: {exc}",
            fix="检查网络或代理,确保能访问 nominatim.openstreetmap.org",
        )


def build_parser():
    parser = argparse.ArgumentParser(description="城市或地点天气面状查询")
    parser.add_argument("--query", help="城市或具体地点")
    parser.add_argument("--days", default=DEFAULT_DAYS, type=int, help="预报天数")
    parser.add_argument("--radius-km", default=DEFAULT_RADIUS_KM, type=float, help="活动半径 km")
    parser.add_argument("--out", metavar="DIR", help="最终报告输出目录")
    parser.add_argument("--resume", metavar="JOB_DIR", help="续跑 TO_AGENT 断点 job_dir")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _build_node_args(query, days, radius_km, out_dir=None) -> dict[str, dict]:
    node_args = {}
    if query is not None:
        node_args["parse_args"] = {"query": query, "days": days, "radius_km": radius_km}
    if out_dir:
        node_args["export"] = {"out_dir": out_dir}
    return node_args


def _emit_envelope(ok, data=None, error=None, started_at=0.0):
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "weather-search",
            "elapsed_ms": int((time.time() - started_at) * 1000),
        },
    }
    print(json.dumps(envelope, ensure_ascii=False))


def _emit_error(error, started_at):
    _emit_envelope(
        False,
        error={"code": error.code, "message": error.message, "retryable": error.retryable},
        started_at=started_at,
    )
    return error.exit_code


def _emit_unexpected(exc, started_at):
    _emit_envelope(
        False,
        error={"code": "unexpected", "message": f"{type(exc).__name__}: {exc}", "retryable": False},
        started_at=started_at,
    )
    return EXIT_RUNTIME


async def _run_to_break(runner, *, resume=False) -> tuple[BreakKind, JobEvent | None]:
    events, break_kind, break_event = await runner.run_to_break(resume=resume)
    for ev in events:
        esflow_event(ev)
    if break_kind == "to_agent" and break_event is not None:
        print(Runner.to_agent_hint(break_event, resume_cmd=_RESUME_CMD), file=sys.stderr)
        print(ADVICE_STYLE_HINT, file=sys.stderr)
    return break_kind, break_event


async def _run_flow(flow_dir, query, days, radius_km, out_dir):
    runner = Runner.load(
        flow_dir,
        node_args=_build_node_args(query, days, radius_km, out_dir),
    )
    break_kind, break_event = await _run_to_break(runner)
    return runner, break_kind, break_event


async def _run_resume(flow_dir, job_dir, out_dir):
    node_args = _build_node_args(None, None, None, out_dir) if out_dir else None
    runner = Runner.load(flow_dir, job_dir=Path(job_dir), node_args=node_args)
    if not runner.has_break_to_agent():
        raise CliError("resume_error", f"无待完成的 TO_AGENT 节点:{job_dir}", EXIT_VALIDATION)
    break_kind, break_event = await _run_to_break(runner, resume=True)
    return runner, break_kind, break_event


def _build_success_data(runner):
    data = {"job_dir": str(runner.job_dir)}
    export = runner.artifacts.get("export")
    if export:
        data["out_path"] = export.get("out_path")
        data["out_dir"] = export.get("out_dir")
    return data


def _build_to_agent_data(runner):
    agent_run = runner.runs.get("agent_advice")
    data = {
        "job_dir": str(runner.job_dir),
        "analyze_grid_artifact": analyze_grid_artifact_path(runner.job_dir),
    }
    if agent_run is not None:
        data["advice_path"] = str(agent_run.output_dir / ADVICE_FILENAME)
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
        _emit_envelope(True, data=_build_to_agent_data(runner), started_at=started_at)
    return exit_code


def main():
    started_at = time.time()
    args = build_parser().parse_args()
    flow_dir = str(Path(__file__).parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.resume:
        return _run_with_envelope(
            lambda: _run_resume(flow_dir, args.resume, args.out),
            started_at,
            build_data=_build_success_data,
        )

    if not (args.query and str(args.query).strip()):
        build_parser().error("首次运行必须提供 --query")

    try:
        pass_check(check_python_version, check_network)
    except FlowCheckError as exc:
        print(exc, file=sys.stderr)
        return EXIT_VALIDATION

    return _run_with_envelope(
        lambda: _run_flow(flow_dir, args.query, args.days, args.radius_km, args.out),
        started_at,
        build_data=_build_success_data,
    )


if __name__ == "__main__":
    raise SystemExit(main())
