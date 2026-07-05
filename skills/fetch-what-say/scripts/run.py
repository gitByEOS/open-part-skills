#!/usr/bin/env python3
"""fetch-what-say 入口:argparse + pass_check 预检 + 启动 esflow runner。

直接跑:python3 scripts/run.py <input>
跑到达 agent_summary 节点退出(exit 2),Agent 写 summary.txt 后:
python3 scripts/run.py --resume <job_dir>
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import shutil
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
    DEFAULT_OUTPUT_DIR,
    DEFAULT_WHISPER_MODEL,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_VALIDATION,
    SCHEMA_VERSION,
    output_schema,
)
from nodes.export_html import generate_viewer


# TO_AGENT 续跑命令模板,{job_dir} 由 Runner.to_agent_hint 填充
_RESUME_CMD = "python3 scripts/run.py --resume {job_dir}"


# —— 预检 ——

def _check_input(value):
    if value:
        return None
    return "缺少 input 位置参数"


def _check_yt_dlp():
    if shutil.which("yt-dlp"):
        return None
    return CheckResult(reason="未安装 yt-dlp", fix="pip install yt-dlp")


def _check_ffmpeg():
    if shutil.which("ffmpeg"):
        return None
    return CheckResult(reason="未安装 ffmpeg", fix="brew install ffmpeg          # macOS\nsudo apt install ffmpeg      # Debian/Ubuntu")


def _check_mlx_whisper():
    if importlib.util.find_spec("mlx_whisper"):
        return None
    return CheckResult(reason="未安装 mlx-whisper", fix="pip install mlx-whisper")


# —— 参数 ——

def build_parser():
    parser = argparse.ArgumentParser(description="抓取 yt-dlp 支持的媒体,生成 transcript 与 viewer")
    parser.add_argument("input", nargs="?", help="yt-dlp 支持的 URL、BV、ep,或本地视频文件")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="输出根目录")
    parser.add_argument("--view", metavar="WORK_DIR", help="生成 viewer.html 并打开浏览器(不进 flow)")
    parser.add_argument("--resume", metavar="JOB_DIR", help="从 job_dir 续跑 TO_AGENT 节点")
    parser.add_argument("--job-dir", metavar="DIR", help="指定 esflow job 目录")
    parser.add_argument("--cookies", help="Netscape cookies.txt;不传时自动使用默认 cookies 目录")
    parser.add_argument("--height", type=int, default=360, help="最高分辨率")
    parser.add_argument("--prefer", choices=["size", "bitrate"], default="size", help="小体积或高码率")
    parser.add_argument("--merge-format", default="mp4", help="合并容器格式")
    parser.add_argument("--transcribe", dest="transcribe", action="store_true", default=True, help="输出 transcript,默认开启")
    parser.add_argument("--no-transcribe", dest="transcribe", action="store_false", help="只下载媒体,不转写")
    parser.add_argument("--model", default=DEFAULT_WHISPER_MODEL, help="mlx-whisper 模型")
    parser.add_argument("--language", default="zh", help="转写语言,如 zh、en、ja")
    parser.add_argument("--dry-run", action="store_true", help="只输出计划")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _build_node_args(args) -> dict[str, dict]:
    """把 CLI 参数按节点 id 聚合,Runner.load 一次注入到对应节点的 self.kwargs。"""
    return {
        "resolve": {
            "input": args.input,
            "out": args.out,
            "cookies": args.cookies,
        },
        "download": {
            "height": args.height,
            "prefer": args.prefer,
            "merge_format": args.merge_format,
        },
        "extract_audio": {"transcribe": args.transcribe},
        "transcribe": {
            "model": args.model,
            "language": args.language,
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
            "tool": "fetch-what-say",
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
    """跑 runner 到断点,批量打印事件,to_agent 时打印 hint。error 由上层 _run_with_envelope 处理。"""
    events, break_kind, break_event = await runner.run_to_break(only=only, resume=resume)
    for event in events:
        esflow_event(event)
    if break_kind == "to_agent" and break_event is not None:
        print(Runner.to_agent_hint(break_event, resume_cmd=_RESUME_CMD), file=sys.stderr)
    return break_kind, break_event


async def _run_flow(flow_dir, output_root, job_dir, args, only=None):
    runner = Runner.load(
        flow_dir,
        output_root=output_root,
        job_dir=job_dir,
        node_args=_build_node_args(args),
    )
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
    plan = artifacts.get("resolve", {})
    download = artifacts.get("download", {})
    transcribe = artifacts.get("transcribe")
    export_html = artifacts.get("export_html")
    data = {
        "video": download.get("video_path") if download else None,
        "cached": download.get("cached", False) if download else False,
        "plan": plan or {},
    }
    if transcribe:
        data["transcripts"] = {"srt": transcribe["srt_path"], "txt": transcribe["txt_path"]}
        data["summary"] = str(Path(transcribe["txt_path"]).parent / "summary.txt")
        data["transcript_cached"] = transcribe.get("cached", False)
    if export_html:
        data["viewer"] = export_html.get("viewer_path")
    return data


def _run_with_envelope(coro_factory, started_at, *, build_data=None):
    """统一封装:asyncio 跑 flow + to_envelope 归一化 break_kind + 异常转 envelope,返回退出码。

    - error:as_exception() 还原异常,CliError 走细粒度 exit_code,其他走 unexpected
    - to_agent:只打印 hint(在 _run_to_break 里),不输出 envelope,返回 2
    - end:to_envelope 出 (0, {status:"end"}),用 _emit_envelope 包成 skill 输出契约
    """
    try:
        runner, break_kind, break_event = asyncio.run(coro_factory())
    except CliError as error:
        return _emit_error(error, started_at)
    except Exception as exc:
        return _emit_unexpected(exc, started_at)

    if break_kind == "error":
        # 框架已序列化异常,as_exception() 还原后走 CliError 细粒度 exit_code
        try:
            raise break_event.as_exception()
        except CliError as error:
            return _emit_error(error, started_at)
        except Exception as exc:
            return _emit_unexpected(exc, started_at)

    # end / to_agent:to_envelope 归一化 exit_code(来自框架,不再硬编码)
    exit_code, _ = Runner.to_envelope(break_kind, break_event)
    if break_kind == "end":
        _emit_envelope(True, data=build_data(runner) if build_data else None, started_at=started_at)
    return exit_code


# —— 主流程 ——

def main():
    started_at = time.time()
    args = build_parser().parse_args()
    flow_dir = str(Path(__file__).parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.view:
        try:
            generate_viewer(args.view)
            return EXIT_OK
        except CliError as error:
            return _emit_error(error, started_at)

    if args.resume:
        return _run_with_envelope(
            lambda: _run_resume(flow_dir, args.resume, args),
            started_at, build_data=_build_success_data,
        )

    # 预检:dry-run 只需 yt-dlp(resolve 取 metadata);普通模式按 transcribe 开关加 ffmpeg/mlx-whisper
    def check_input():
        return _check_input(args.input)

    checks = [check_input, _check_yt_dlp]
    if not args.dry_run:
        checks.append(_check_ffmpeg)
        if args.transcribe:
            checks.append(_check_mlx_whisper)
    try:
        pass_check(*checks)
    except FlowCheckError as exc:
        print(f"预检失败:\n{exc}", file=sys.stderr)
        return EXIT_VALIDATION

    output_root = Path(args.out).expanduser() / ".esflow-jobs"
    job_dir = Path(args.job_dir) if args.job_dir else None

    if args.dry_run:
        return _run_with_envelope(
            lambda: _run_flow(flow_dir, output_root, job_dir, args, only={"resolve"}),
            started_at, build_data=lambda r: {"dry_run": True, "plan": r.artifacts.get("resolve", {})},
        )

    # --no-transcribe 走 accept 级联:extract_audio.accept 返回 False → 下游 transcribe/export_html 跳过
    # 不再用 only={"download"} 双轨表达,业务跳过只留 accept 一处
    return _run_with_envelope(
        lambda: _run_flow(flow_dir, output_root, job_dir, args),
        started_at, build_data=_build_success_data,
    )


if __name__ == "__main__":
    raise SystemExit(main())
