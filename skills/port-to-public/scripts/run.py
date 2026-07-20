#!/usr/bin/env python3
"""port-to-public CLI：以 esflow 编排 Quick Tunnel 的完整生命周期。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from esflow import Runner, esflow_event, pass_check

from common import (
    DEFAULT_TIMEOUT,
    DEFAULT_TTL,
    DEFAULT_VERIFY_TIMEOUT,
    SCHEMA_VERSION,
    TOOL_NAME,
    check_cloudflared,
    json_error,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将本机 loopback HTTP(S) 服务临时暴露到公网")
    parser.add_argument("action", nargs="?", choices=["start", "status", "verify", "stop"])
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--port", type=int, help="本机 loopback HTTP 服务端口")
    target.add_argument("--url", help="本机 loopback HTTP(S) 服务 URL")
    parser.add_argument("--confirm-public", action="store_true", help="确认该公网 URL 无认证且持有者可访问")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="自动停止秒数，默认 43200（12 小时）")
    parser.add_argument("--path", default="/", help="verify 的同源相对路径，默认 /")
    parser.add_argument("--expect", help="verify 响应必须包含的文本")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="启动 tunnel 超时秒数")
    parser.add_argument("--verify-timeout", type=int, default=DEFAULT_VERIFY_TIMEOUT, help="公网验证超时秒数")
    parser.add_argument("--protocol", choices=["http2", "quic"], default="http2")
    parser.add_argument("--no-tls-verify", action="store_true", help="允许本机自签名 HTTPS")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def output_schema() -> dict:
    # 标准 esflow skill 信封：{ok, data, error, meta}，编排器零适配复用。
    return {
        "ok": "boolean",
        "data": {
            "action": "start | status | verify | stop",
            "status": "started | running | verified | stopped | already_stopped",
            "local_url": "string",
            "public_url": "string | null",
            "running": "boolean",
            "pid": "number | null",
            "expires_at": "number | null (epoch seconds)",
            "verification": {
                "ok": "boolean",
                "url": "string",
                "http_status": "number",
                "expect_matched": "boolean | null",
                "latency_ms": "number",
            },
            "stop": {"stopped": "boolean", "already_stopped": "boolean", "pid": "number | null", "reason": "string | null"},
            "stop_command": "string",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean", "_null": "error 为 null 当 ok=true"} ,
        "meta": {"schema_version": SCHEMA_VERSION, "tool": TOOL_NAME, "elapsed_ms": "number"},
    }


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def meta(started_at: float) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "elapsed_ms": int((time.monotonic() - started_at) * 1000),
    }


def ok_envelope(data: dict, started_at: float) -> dict:
    return {"ok": True, "data": data, "error": None, "meta": meta(started_at)}


def error_envelope(exc: Exception, started_at: float) -> dict:
    return {"ok": False, "data": None, "error": json_error(exc), "meta": meta(started_at)}


def node_args(args: argparse.Namespace) -> dict[str, dict]:
    return {
        "validate_request": {
            "action": args.action,
            "port": args.port,
            "url": args.url,
            "confirm_public": args.confirm_public,
            "ttl": args.ttl,
            "path": args.path,
            "expect": args.expect,
            "timeout": args.timeout,
            "verify_timeout": args.verify_timeout,
            "protocol": args.protocol,
            "no_tls_verify": args.no_tls_verify,
            "skill_root": str(Path(__file__).resolve().parent.parent),
        }
    }


async def run_flow(args: argparse.Namespace) -> dict:
    flow_dir = str(Path(__file__).parent)
    # validate_request 先推导内部 session；这里不给 job_dir，避免 CLI 暴露 --out。
    runner = Runner.load(flow_dir, node_args=node_args(args))
    events, kind, break_event = await runner.run_to_break()
    for event in events:
        esflow_event(event)
    if kind == "error" and break_event is not None:
        raise break_event.as_exception()
    result = runner.artifacts.get("render_result")
    if not result:
        raise RuntimeError("flow 未生成 render_result")
    return result


def main() -> int:
    started_at = time.monotonic()
    parser = build_parser()
    args = parser.parse_args()

    if args.schema:
        emit(output_schema())
        return 0
    if not args.action:
        parser.error("缺少动作：start、status、verify 或 stop")
    if args.port is None and args.url is None:
        parser.error("必须提供 --port 或 --url")

    try:
        pass_check(check_cloudflared)
        data = asyncio.run(run_flow(args))
    except Exception as exc:
        emit(error_envelope(exc, started_at))
        return 1

    emit(ok_envelope(data, started_at))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
