#!/usr/bin/env python3
"""holiday-of-12306 入口:argparse + pass_check 预检 + 启动 esflow runner。

直接跑:python3 scripts/run.py <出发站> [返程站] [年份]
DAG:holidays ∥ resolve_stations → query_sale_time → export_html
--update 走 only={"holidays"} 的 verbose 模式,升级库并自检,不生成日历。
无 TO_AGENT 断点,一次跑完输出抢票日历 HTML 并弹出浏览器。
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from esflow import (
    CheckResult,
    FlowCheckError,
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


_DEFAULT_OUT = str(Path.home() / "Downloads" / "ticket-calendar")


def _check_departure(value):
    if value:
        return None
    return "缺少出发站参数"


def _check_requests():
    if importlib.util.find_spec("requests"):
        return None
    return CheckResult(reason="未安装 requests", fix="pip install requests")


def parse_route_args(departure, arg2, arg3):
    """解析 出发站 [返程站] [年份]。"""
    if arg2 is None:
        return departure, None, date.today().year
    if re.fullmatch(r"\d{4}", arg2):
        return departure, None, int(arg2)
    year = arg3 if arg3 is not None else date.today().year
    return departure, arg2, year


def build_parser():
    parser = argparse.ArgumentParser(description="12306 节假日抢票日历(出发站 + 可选返程站)")
    parser.add_argument("departure", nargs="?", help="出发站名,如 北京南")
    parser.add_argument("return_station", nargs="?", help="返程站名,如 天津西;省略则仅生成去程")
    parser.add_argument("year", nargs="?", type=int, help="目标年份,默认当前年")
    parser.add_argument("--update", action="store_true", help="仅升级 chinesecalendar 并自检,不生成日历")
    parser.add_argument("--skip-update", action="store_true", help="跳过默认的节假日库同步")
    parser.add_argument("--out", default=_DEFAULT_OUT, help="HTML 输出目录")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--job-dir", metavar="DIR", help="指定 esflow job 目录")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _build_node_args(args, departure, return_station, year) -> dict[str, dict]:
    """把 CLI 参数按节点 id 聚合,Runner.load 一次注入到对应节点的 self.kwargs。"""
    return {
        "holidays": {"year": year, "skip_update": args.skip_update},
        "resolve_stations": {"departure": departure, "return_station": return_station},
        "export_html": {"out": args.out, "open": not args.no_open},
    }


# —— 输出 ——

def _emit_envelope(ok, data=None, error=None, started_at=0.0):
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "holiday-of-12306",
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

async def _run_flow(flow_dir, output_root, job_dir, node_args, only=None):
    runner = Runner.load(
        flow_dir,
        output_root=output_root,
        job_dir=job_dir,
        node_args=node_args,
    )
    events, break_kind, break_event = await runner.run_to_break(only=only)
    for event in events:
        esflow_event(event)
    return runner, break_kind, break_event


def _run_with_envelope(coro_factory, started_at, *, build_data=None):
    """统一封装:asyncio 跑 flow + 异常转 envelope,返回退出码。"""
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
    return exit_code


def _build_success_data(runner):
    export = runner.artifacts.get("export_html")
    if not export:
        return None
    return {
        "html_path": export["html_path"],
        "departure": export["departure"],
        "return": export["return"],
        "year": export["year"],
        "festivals": export["festivals"],
    }


def _run_update(flow_dir, args, started_at):
    """--update:走 only={"holidays"} 的 verbose flow,升级库并自检,不生成日历。"""
    node_args = {
        "holidays": {"year": date.today().year, "skip_update": False, "verbose": True},
    }
    output_root = Path(args.out).expanduser() / ".esflow-jobs"
    job_dir = Path(args.job_dir) if args.job_dir else None
    return _run_with_envelope(
        lambda: _run_flow(flow_dir, output_root, job_dir, node_args, only={"holidays"}),
        started_at, build_data=lambda r: {"update": True, "holidays": r.artifacts.get("holidays")},
    )


# —— 主流程 ——

def main():
    started_at = time.time()
    args = build_parser().parse_args()
    flow_dir = str(Path(__file__).parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.update:
        try:
            pass_check(_check_requests)
        except FlowCheckError as exc:
            print(f"预检失败:\n{exc}", file=sys.stderr)
            return EXIT_VALIDATION
        return _run_update(flow_dir, args, started_at)

    try:
        pass_check(lambda: _check_departure(args.departure), _check_requests)
    except FlowCheckError as exc:
        print(f"预检失败:\n{exc}", file=sys.stderr)
        return EXIT_VALIDATION

    departure, return_station, year = parse_route_args(
        args.departure, args.return_station, args.year,
    )

    node_args = _build_node_args(args, departure, return_station, year)
    output_root = Path(args.out).expanduser() / ".esflow-jobs"
    job_dir = Path(args.job_dir) if args.job_dir else None

    return _run_with_envelope(
        lambda: _run_flow(flow_dir, output_root, job_dir, node_args),
        started_at, build_data=_build_success_data,
    )


if __name__ == "__main__":
    raise SystemExit(main())
