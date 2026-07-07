#!/usr/bin/env python3
"""blog-narrator 入口:argparse 子命令(preview/tts)+ 启动 esflow runner。

单 flow 双路径,mode 由子命令决定,注入各节点 accept 据此跳过:
- preview:parse_md → export_preview(TTS 链全 skip)
- tts:parse_md → split → gen → match(条件) → merge(export_preview skip)

直接跑:
  python3 scripts/run.py preview <input.md> <output.html> [--rate 1.15] [--open]
  python3 scripts/run.py tts <input.md> <work_dir> [--voice xiaoxiao|xiaoyi] [--rate 1.175] [--open]
DAG 见 flow.py。无 TO_AGENT 断点,一次跑完。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from esflow import (
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


def _check_input(input_path: Path):
    if input_path.is_file():
        return None
    return f"输入文件不存在:{input_path}"


def build_parser():
    parser = argparse.ArgumentParser(description="博客逐行披露演示 + 分段配音")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    sub = parser.add_subparsers(dest="mode")

    p_preview = sub.add_parser("preview", help="轻量预览 HTML,无预录音")
    p_preview.add_argument("input", help="输入 Markdown")
    p_preview.add_argument("output", help="输出 HTML 路径")
    p_preview.add_argument("--rate", type=float, default=1.15, help="默认语速")
    p_preview.add_argument("--open", action="store_true", help="生成后打开浏览器")

    p_tts = sub.add_parser("tts", help="Edge TTS 分段配音合并 HTML")
    p_tts.add_argument("input", help="输入 Markdown")
    p_tts.add_argument("work_dir", help="工作目录(存 src.md/srt.md/audio/产物)")
    p_tts.add_argument("--voice", default="xiaoxiao", choices=["xiaoxiao", "xiaoyi"], help="音色")
    p_tts.add_argument("--rate", type=float, default=1.175, help="语速")
    p_tts.add_argument("--open", action="store_true", help="生成后打开浏览器")
    p_tts.add_argument("--from", dest="from_node", metavar="NODE", help="从指定节点续跑该节点及下游,上游从 --job-dir 加载")
    p_tts.add_argument("--job-dir", metavar="DIR", help="--from 续跑时必填,指向上次 job 目录")
    return parser


def _build_node_args(args) -> dict[str, dict]:
    """把 CLI 参数按节点 id 聚合,Runner.load 一次注入到对应节点的 self.kwargs。"""
    input_path = str(Path(args.input).expanduser().resolve())
    common = {"mode": args.mode, "input": input_path}
    if args.mode == "preview":
        output_path = str(Path(args.output).expanduser().resolve())
        return {
            "parse_md": common,
            "export_preview": {
                "mode": args.mode,
                "output": output_path,
                "rate": args.rate,
                "open": args.open,
            },
            "split": {"mode": args.mode},
            "gen": {},
            "match": {},
            "merge": {},
        }
    work_dir = str(Path(args.work_dir).expanduser().resolve())
    return {
        "parse_md": common,
        "export_preview": {"mode": args.mode},
        "split": {"mode": args.mode, "work_dir": work_dir},
        "gen": {"voice": args.voice, "rate": args.rate},
        "match": {},
        "merge": {"open": args.open},
    }


def _default_output_root(args) -> Path:
    if args.mode == "preview":
        base = Path(args.output).expanduser().resolve().parent
    else:
        base = Path(args.work_dir).expanduser().resolve()
    return base / ".esflow-jobs"


def _build_success_data(runner, mode):
    if mode == "preview":
        art = runner.artifacts.get("export_preview")
    else:
        art = runner.artifacts.get("merge")
    return art


# —— flow 执行 ——


async def _run_flow(flow_dir, output_root, job_dir, node_args, from_node=None):
    runner = Runner.load(
        flow_dir,
        output_root=output_root,
        job_dir=job_dir,
        node_args=node_args,
    )
    events, break_kind, break_event = await runner.run_to_break(from_node=from_node)
    for event in events:
        esflow_event(event)
    return runner, break_kind, break_event


def _emit_envelope(ok, data=None, error=None, started_at=0.0):
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "blog-narrator",
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
    return exit_code


def main():
    started_at = time.time()
    args = build_parser().parse_args()
    flow_dir = str(Path(__file__).parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.mode is None:
        parser.error("需要子命令 preview 或 tts(或用 --schema 查看契约)")

    input_path = Path(args.input).expanduser().resolve()
    try:
        pass_check(lambda: _check_input(input_path))
    except FlowCheckError as exc:
        print(f"预检失败:\n{exc}", file=sys.stderr)
        return EXIT_VALIDATION

    node_args = _build_node_args(args)
    output_root = _default_output_root(args)
    from_node = getattr(args, "from_node", None)
    job_dir = Path(getattr(args, "job_dir", None)) if getattr(args, "job_dir", None) else None

    if from_node and not job_dir:
        print("--from 续跑必须配合 --job-dir 指向上次 job 目录", file=sys.stderr)
        return EXIT_VALIDATION

    return _run_with_envelope(
        lambda: _run_flow(flow_dir, output_root, job_dir, node_args, from_node=from_node),
        started_at,
        build_data=lambda r: _build_success_data(r, args.mode),
    )


if __name__ == "__main__":
    raise SystemExit(main())
