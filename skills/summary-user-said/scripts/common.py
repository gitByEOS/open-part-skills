"""summary-user-said 公共契约：参数、路径、统计与 stdout envelope。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, time as day_time, timedelta
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "1.0.0"
EXIT_OK, EXIT_RUNTIME, EXIT_TO_AGENT, EXIT_VALIDATION = 0, 1, 2, 3
SUMMARY_FILENAME = "summary.json"
BRIEF_FILENAME = "_agent_summary_brief.json"
MESSAGES_FILENAME = "messages.jsonl"
DEFAULT_SOURCES = ("cursor",)
SOURCE_ORDER = ("cursor", "claude", "codex")
SOURCE_ROOTS = {
    "cursor": Path.home() / ".cursor" / "projects",
    "claude": Path.home() / ".claude" / "projects",
    "codex": Path.home() / ".codex" / "sessions",
}


class CliError(Exception):
    """携带稳定错误码的用户输入或业务校验错误。"""

    def __init__(self, code: str, message: str, exit_code: int = EXIT_VALIDATION):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


class StrictArgumentParser(argparse.ArgumentParser):
    """让 argparse 错误进入统一 JSON envelope。"""

    def error(self, message):
        raise CliError("invalid_arguments", f"{message}\n用法：{self.format_usage().strip()}")


def positive_integer(value: str) -> int:
    """解析不接受符号、零或空白的正整数。"""
    if not re.fullmatch(r"[1-9][0-9]*", value or ""):
        raise argparse.ArgumentTypeError("周期数必须是正整数")
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = StrictArgumentParser(
        description="汇总本地 Agent 历史中的用户发言",
        allow_abbrev=False,
    )
    source = parser.add_argument_group("数据源")
    source.add_argument("--cursor", action="append_const", const="cursor", dest="sources")
    source.add_argument("--claude", action="append_const", const="claude", dest="sources")
    source.add_argument("--codex", action="append_const", const="codex", dest="sources")
    source.add_argument("--dir", action="append", metavar="DIR", dest="custom_dirs")

    period = parser.add_mutually_exclusive_group()
    period.add_argument("--week", action="append", type=positive_integer, metavar="N")
    period.add_argument("--day", action="append", type=positive_integer, metavar="N")

    parser.add_argument("--resume", metavar="JOB_DIR", help="续跑 TO_AGENT 断点")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _local_timezone_name() -> str:
    """优先取得 IANA 时区，避免仅记录含糊的 CST。"""
    tz_env = os.environ.get("TZ")
    if tz_env:
        try:
            ZoneInfo(tz_env)
            return tz_env
        except Exception:
            pass
    try:
        resolved = Path("/etc/localtime").resolve()
        parts = resolved.parts
        index = parts.index("zoneinfo")
        name = "/".join(parts[index + 1 :])
        ZoneInfo(name)
        return name
    except (OSError, ValueError, Exception):
        pass
    local = datetime.now().astimezone().tzinfo
    key = getattr(local, "key", None)
    return key or str(local)


def _timezone(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        return datetime.now().astimezone().tzinfo


def _period_bounds(kind: str, count: int, now: datetime) -> tuple[datetime, datetime]:
    if kind == "day":
        end_date = now.date()
        start_date = end_date - timedelta(days=count)
    else:
        end_date = now.date() - timedelta(days=now.weekday())
        start_date = end_date - timedelta(weeks=count)
    start = datetime.combine(start_date, day_time.min, tzinfo=now.tzinfo)
    end = datetime.combine(end_date, day_time.min, tzinfo=now.tzinfo)
    return start, end


def _period_keys(kind: str, count: int, now: datetime) -> list[str]:
    if kind == "day":
        first = now.date() - timedelta(days=count)
        return [(first + timedelta(days=index)).isoformat() for index in range(count)]
    first = now.date() - timedelta(days=now.weekday(), weeks=count)
    return [f"{(first + timedelta(weeks=index)).isoformat()}_to_{(first + timedelta(weeks=index, days=6)).isoformat()}" for index in range(count)]


def period_key(kind: str, instant: datetime) -> str:
    if kind == "day":
        return instant.date().isoformat()
    monday = instant.date() - timedelta(days=instant.weekday())
    return f"{monday.isoformat()}_to_{(monday + timedelta(days=6)).isoformat()}"


def _source_label(sources: tuple[str, ...], custom_dir: str | None) -> str:
    if custom_dir:
        digest = hashlib.sha256(custom_dir.encode("utf-8")).hexdigest()[:10]
        return f"dir-{digest}"
    return "-".join(sources)


def _normalized_source_selection(args) -> tuple[tuple[str, ...], str | None]:
    sources = tuple(args.sources or ())
    custom_dirs = tuple(args.custom_dirs or ())
    if len(sources) != len(set(sources)):
        raise CliError("invalid_arguments", "数据源参数不可重复")
    if len(custom_dirs) > 1:
        raise CliError("invalid_arguments", "--dir 不可重复")
    if sources and custom_dirs:
        raise CliError("invalid_arguments", "--dir 与 --cursor/--claude/--codex 互斥")
    if custom_dirs:
        custom = Path(custom_dirs[0]).expanduser()
        try:
            resolved = custom.resolve(strict=True)
        except OSError as exc:
            raise CliError("invalid_source", f"数据目录不可用：{custom}：{exc}") from exc
        if not resolved.is_dir():
            raise CliError("invalid_source", f"--dir 必须指向目录：{resolved}")
        return (), str(resolved)
    selected = tuple(name for name in SOURCE_ORDER if name in (sources or DEFAULT_SOURCES))
    return selected, None


def _period_selection(args) -> tuple[str, int]:
    if args.day is not None:
        if len(args.day) != 1:
            raise CliError("invalid_arguments", "--day 不可重复")
        return "day", args.day[0]
    if args.week is not None:
        if len(args.week) != 1:
            raise CliError("invalid_arguments", "--week 不可重复")
        return "week", args.week[0]
    return "week", 1


@dataclass(frozen=True)
class Request:
    """首跑冻结的完整请求，续跑时不重新计算窗口。"""

    sources: tuple[str, ...]
    custom_dir: str | None
    custom_source_label: str | None
    period_kind: str
    period_count: int
    timezone: str
    now: str
    window_start: str
    window_end: str
    period_keys: tuple[str, ...]
    output_dir: str
    summary_path: str
    original_path: str
    base_name: str
    command: str

    def as_dict(self) -> dict:
        data = dict(self.__dict__)
        data["sources"] = list(self.sources)
        data["period_keys"] = list(self.period_keys)
        return data


def build_request(args, *, cwd: Path | None = None, now: datetime | None = None) -> Request:
    sources, custom_dir = _normalized_source_selection(args)
    kind, count = _period_selection(args)
    timezone_name = _local_timezone_name()
    tz = _timezone(timezone_name)
    current = (now or datetime.now(tz)).astimezone(tz)
    start, end = _period_bounds(kind, count, current)
    periods = tuple(_period_keys(kind, count, current))
    output_dir = (cwd or Path.cwd()).resolve()
    label = _source_label(sources, custom_dir)
    base = f"{label}-{kind}-{start.date().isoformat()}_to_{end.date().isoformat()}"
    summary_path = output_dir / f"{base}.md"
    original_path = output_dir / f"{base}.messages.md"
    conflicts = [str(path) for path in (summary_path, original_path) if path.exists()]
    if conflicts:
        raise CliError("output_conflict", "目标产物已存在，拒绝覆盖：" + "、".join(conflicts))
    command_sources = [f"--{name}" for name in sources]
    if custom_dir:
        command_sources = ["--dir", custom_dir]
    command = "summary-user-said " + " ".join(command_sources + [f"--{kind}", str(count)])
    return Request(
        sources=sources,
        custom_dir=custom_dir,
        custom_source_label=label if custom_dir else None,
        period_kind=kind,
        period_count=count,
        timezone=timezone_name,
        now=current.isoformat(),
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        period_keys=periods,
        output_dir=str(output_dir),
        summary_path=str(summary_path),
        original_path=str(original_path),
        base_name=base,
        command=command,
    )


def request_from_dict(data: dict) -> Request:
    data = dict(data)
    data["sources"] = tuple(data.get("sources") or ())
    data["period_keys"] = tuple(data.get("period_keys") or ())
    return Request(**data)


def parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("时间缺少时区")
    return parsed


def emit_envelope(ok: bool, *, data=None, error=None, started_at=0.0) -> None:
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "summary-user-said",
            "elapsed_ms": int((time.time() - started_at) * 1000),
        },
    }
    print(json.dumps(envelope, ensure_ascii=False))


def output_schema() -> None:
    print(json.dumps({
        "ok": "boolean",
        "data": {
            "status": "end | to_agent",
            "job_dir": "string",
            "summary_path": "string",
            "original_path": "string",
            "brief_path": "string，仅 to_agent",
            "messages_path": "string，仅 to_agent，保留原文",
            "agent_summary_path": "string，仅 to_agent",
            "stats": "object",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "2": "to_agent", "3": "validation"},
    }, ensure_ascii=False, indent=2))


def json_dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
