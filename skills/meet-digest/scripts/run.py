#!/usr/bin/env python3
"""会议转写提炼入口。

用法:
    python3 /abs/meet-digest/scripts/run.py --path <wav或目录> --out <job_dir>
    python3 /abs/meet-digest/scripts/run.py --resume <job_dir>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import shutil
import sys
import time
from pathlib import Path

from common import (
    BRIEF_FILENAME,
    DIGEST_HINT,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_VALIDATION,
    MEET_DRAFT,
    SCHEMA_VERSION,
    TOOL_NAME,
    CliError,
    output_schema,
)
from local_load import hop_to_local_python

hop_to_local_python()

from esflow import (  # noqa: E402
    CheckResult,
    FlowCheckError,
    Runner,
    esflow_event,
    pass_check,
)

def resume_cmd_template() -> str:
    python = shlex.quote(sys.executable)
    script = shlex.quote(str(Path(__file__).resolve()))
    return f"{python} {script} --resume \"{{job_dir}}\""


def check_python_version() -> CheckResult | None:
    if sys.version_info >= (3, 10):
        return None
    return CheckResult(
        reason=f"需要 Python >= 3.10,当前 {sys.version_info.major}.{sys.version_info.minor}",
        fix="升级 Python 到 3.10+",
    )


def check_faster_whisper() -> CheckResult | None:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return CheckResult(
            reason="未安装 faster-whisper",
            fix="pip install faster-whisper",
        )
    return None


def check_ffmpeg_backend() -> CheckResult | None:
    if shutil.which("ffmpeg"):
        return None
    try:
        import imageio_ffmpeg

        if imageio_ffmpeg.get_ffmpeg_exe():
            return None
    except Exception:
        pass
    return CheckResult(
        reason="找不到 ffmpeg",
        fix="pip install imageio-ffmpeg",
    )


def build_parser():
    parser = argparse.ArgumentParser(description="会议 wav 转写并提炼总结")
    parser.add_argument("--path", help="wav 文件或只含一个 wav 的目录")
    parser.add_argument("--out", metavar="DIR", help="esflow job 目录，首次必填，续跑只吃这个目录")
    parser.add_argument("--fresh", action="store_true", help="清空旧稿后整段重转")
    parser.add_argument("--name", help="最终总结文件名")
    parser.add_argument("--resume", metavar="JOB_DIR", help="续跑 TO_AGENT 节点")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _build_node_args(path, fresh, name, skill_dir, job_dir):
    args = {
        "resolve_runtime": {"skill_dir": skill_dir},
        "agent_digest": {"job_dir": str(job_dir)},
    }
    if path is not None:
        args["resolve_source"] = {
            "path": path,
            "fresh": bool(fresh),
            "name": name,
        }
    return args


def _emit_envelope(ok, data=None, error=None, started_at=0.0):
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL_NAME,
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


async def _run_to_break(runner, *, resume=False):
    events, break_kind, break_event = await runner.run_to_break(resume=resume)
    for ev in events:
        esflow_event(ev)
    if break_kind == "to_agent" and break_event is not None:
        print(Runner.to_agent_hint(break_event, resume_cmd=resume_cmd_template()), file=sys.stderr)
        print(DIGEST_HINT, file=sys.stderr)
    return break_kind, break_event


async def _run_flow(flow_dir, path, fresh, name, skill_dir, job_dir):
    runner = Runner.load(
        flow_dir,
        job_dir=job_dir,
        node_args=_build_node_args(path, fresh, name, skill_dir, job_dir),
    )
    break_kind, break_event = await _run_to_break(runner)
    return runner, break_kind, break_event


async def _run_resume(flow_dir, job_dir):
    runner = Runner.load(flow_dir, job_dir=Path(job_dir))
    if not runner.has_break_to_agent():
        raise CliError("resume_error", f"无待完成的 TO_AGENT 节点:{job_dir}", EXIT_VALIDATION)
    break_kind, break_event = await _run_to_break(runner, resume=True)
    return runner, break_kind, break_event


def _build_success_data(runner):
    data = {"job_dir": str(runner.job_dir)}
    export = runner.artifacts.get("export_meet") or {}
    transcribe = runner.artifacts.get("transcribe") or {}
    if transcribe:
        data["wav"] = transcribe.get("wav")
        data["srt"] = transcribe.get("srt")
        data["whole"] = transcribe.get("whole")
    if export:
        data["meet_path"] = export.get("meet_path")
        data["wav"] = export.get("wav") or data.get("wav")
        data["srt"] = export.get("srt") or data.get("srt")
        data["whole"] = export.get("whole") or data.get("whole")
    return data


def _build_to_agent_data(runner):
    transcribe = runner.artifacts.get("transcribe") or {}
    agent_run = runner.runs.get("agent_digest")
    data = {
        "job_dir": str(runner.job_dir),
        "wav": transcribe.get("wav"),
        "srt": transcribe.get("srt"),
        "whole": transcribe.get("whole"),
    }
    if agent_run is not None:
        data["brief_path"] = str(Path(agent_run.output_dir) / BRIEF_FILENAME)
        data["draft_path"] = str(Path(agent_run.output_dir) / MEET_DRAFT)
    return data


def _run_with_envelope(coro_factory, started_at):
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
        _emit_envelope(True, data=_build_success_data(runner), started_at=started_at)
    elif break_kind == "to_agent":
        _emit_envelope(True, data=_build_to_agent_data(runner), started_at=started_at)
    return exit_code


def main():
    started_at = time.time()
    args = build_parser().parse_args()
    scripts_dir = Path(__file__).resolve().parent
    flow_dir = str(scripts_dir)
    skill_dir = str(scripts_dir.parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.resume:
        return _run_with_envelope(
            lambda: _run_resume(flow_dir, args.resume),
            started_at,
        )

    if not (args.path and str(args.path).strip()):
        build_parser().error("首次运行必须提供 --path")

    if not (args.out and str(args.out).strip()):
        return _emit_error(
            CliError("out_missing", "首次运行必须提供 --out <job_dir>", EXIT_VALIDATION),
            started_at,
        )

    try:
        pass_check(check_python_version, check_faster_whisper, check_ffmpeg_backend)
    except FlowCheckError as exc:
        print(exc, file=sys.stderr)
        return EXIT_VALIDATION

    job_dir = Path(args.out).expanduser().resolve()
    return _run_with_envelope(
        lambda: _run_flow(
            flow_dir,
            args.path,
            args.fresh,
            args.name,
            skill_dir,
            job_dir,
        ),
        started_at,
    )


if __name__ == "__main__":
    raise SystemExit(main())
