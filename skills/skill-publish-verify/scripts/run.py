#!/usr/bin/env python3
"""skill-publish-verify 入口:argparse + pass_check 预检 + 启动 esflow runner。

直接跑:python3 scripts/run.py <case.json>
跑到 agent_run 节点退出(exit 2),Agent 读 _agent_run_brief.json 使用 skill
并写 run_record.json 后:
python3 scripts/run.py --resume <job_dir>
跑到 agent_report 节点再退出(exit 2),Agent 读 _agent_report_brief.json
写 skill_verify_report.md 后再 --resume 收尾。

work_dir = esflow job_dir = /tmp/skill-publish-verify/<job_id>,首跑结束(含
to_agent)持久化 _case.json 供 --resume 重建 node_args;end/error 且非 --keep
时极简清理(只保留 run_record.artifacts 指向的产物 + skill_verify_report.md,
其余全删),envelope 在清理后构造。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import shutil
import sys
import time
from pathlib import Path

from esflow import (
    CheckResult,
    FlowCheckError,
    Runner,
    esflow_event,
    pass_check,
)

from common import (
    CASE_FILE,
    CliError,
    DEFAULT_WORK_ROOT,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_VALIDATION,
    REPORT_FILE,
    RUN_RECORD_FILE,
    SCHEMA_VERSION,
    output_schema,
)
from case_schema import parse_case


_RESUME_CMD = "python3 scripts/run.py --resume {job_dir}"


def _check_python3():
    if shutil.which("python3"):
        return None
    return CheckResult(reason="未找到 python3", fix="安装 python3 且加入 PATH")


def build_parser():
    parser = argparse.ArgumentParser(description="发布前黑盒验证:隔离环境 + agent 使用 skill + 事实汇报")
    parser.add_argument("case", nargs="?", help="用例 JSON 路径")
    parser.add_argument("--resume", metavar="JOB_DIR", help="从 job_dir 续跑 TO_AGENT 节点")
    parser.add_argument("--keep", action="store_true", help="保留 venv 供人工复核(默认结束清理 venv)")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    return parser


def _build_node_args(case, work_dir):
    """把 case + work_dir 按节点 id 聚合,Runner.load 一次注入。"""
    return {
        "isolate_env": {"work_dir": str(work_dir)},
        "copy_skill": {"skill_path": case["skill_path"]},
        "agent_run": {"demand": case["demand"]},
    }


# —— 输出 ——

def _emit_envelope(ok, data=None, error=None, started_at=0.0):
    envelope = {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "skill-publish-verify",
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


# —— case 持久化(供 --resume 重建 node_args)——

def _persist_case(work_dir, case):
    if not work_dir.exists():
        return
    (work_dir / CASE_FILE).write_text(
        json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_case_from_job(job_dir):
    path = Path(job_dir) / CASE_FILE
    if not path.is_file():
        raise CliError("resume_error", f"job_dir 下找不到 {CASE_FILE}:{path}", EXIT_VALIDATION)
    return json.loads(path.read_text(encoding="utf-8"))


def _cleanup_job(work_dir, runner=None):
    """end/error 后极简清理:只保留 run_record.artifacts 指向的产物 + 报告。

    精确保留:run_record.artifacts 中落在 work_dir 内的具体文件 + 报告。
    删除 work_dir 内所有其他文件(含 .esflow/、src.md、srt.md、venv、
    skill 副本、brief、run_record.json、verify_facts.json 等),再删空目录。
    to_agent 中断时不调用——还要 --resume 跑后续节点。

    keep_files 注入 runner.artifacts['_cleanup_keep'],供 _build_success_data
    构造 envelope.data.artifacts 时读取,避免 rglob 无差别扫进 esflow 内部状态。
    """
    work_dir = Path(work_dir)
    work_root = work_dir.resolve()
    keep_files = {(work_dir / REPORT_FILE).resolve()}
    record_path = work_dir / RUN_RECORD_FILE
    if record_path.is_file():
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            for raw in record.get("artifacts") or []:
                p = Path(str(raw)).resolve()
                if p.is_relative_to(work_root):
                    keep_files.add(p)
        except (OSError, json.JSONDecodeError):
            pass

    # 删除非 keep 文件
    for p in work_dir.rglob("*"):
        if p.is_file() and p.resolve() not in keep_files:
            try:
                p.unlink()
            except OSError:
                pass
    # 删空目录(深度优先,子目录先删)
    for p in sorted(work_dir.rglob("*"), reverse=True):
        if p.is_dir():
            try:
                if not any(p.iterdir()):
                    p.rmdir()
            except OSError:
                pass

    if runner is not None:
        runner.artifacts["_cleanup_keep"] = sorted(str(p) for p in keep_files)


def _artifact_paths_from_keep(keep_list):
    """从 keep 列表返回仍存在且非报告的产物路径。"""
    return sorted(p for p in keep_list if Path(p).exists())


def _artifact_paths_fallback(work_dir):
    """--keep 模式未清理:从 run_record 读 artifacts,只报 run_record 列出的产物。

    不再 rglob 全扫——避免 .esflow/、src.md、srt.md 等内部状态污染 envelope。
    """
    work_dir = Path(work_dir)
    work_root = work_dir.resolve()
    record_path = work_dir / RUN_RECORD_FILE
    if not record_path.is_file():
        return []
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    report = str((work_dir / REPORT_FILE).resolve())
    paths = []
    for raw in record.get("artifacts") or []:
        p = Path(str(raw)).resolve()
        if p.is_relative_to(work_root) and p.exists() and str(p) != report:
            paths.append(str(p))
    return sorted(paths)


# —— flow 执行 ——

async def _run_to_break(runner, only=None, resume=False):
    events, break_kind, break_event = await runner.run_to_break(only=only, resume=resume)
    for event in events:
        esflow_event(event)
    if break_kind == "to_agent" and break_event is not None:
        print(Runner.to_agent_hint(break_event, resume_cmd=_RESUME_CMD), file=sys.stderr)
    return break_kind, break_event


async def _run_flow(flow_dir, output_root, job_dir, node_args, only=None):
    runner = Runner.load(flow_dir, output_root=output_root, job_dir=job_dir, node_args=node_args)
    break_kind, break_event = await _run_to_break(runner, only=only)
    return runner, break_kind, break_event


async def _run_resume(flow_dir, job_dir, node_args):
    runner = Runner.load(flow_dir, job_dir=job_dir, node_args=node_args)
    if not runner.has_break_to_agent():
        raise CliError("resume_error", f"无待完成的 TO_AGENT 节点:{job_dir}", EXIT_VALIDATION)
    break_kind, break_event = await _run_to_break(runner, resume=True)
    return runner, break_kind, break_event


def _build_success_data(runner, work_dir):
    """清理后构造 envelope.data:只带仍存在的用户产物路径。

    artifacts 来源优先级:
    1. runner.artifacts['_cleanup_keep'] —— 清理时注入,只含 run_record.artifacts
       中清理后仍存在的文件(精确,不含 .esflow/、src.md、srt.md 等内部状态)
    2. run_record.json fallback —— --keep 模式未清理时读 run_record.artifacts

    不再 rglob 全扫 work_dir,避免 esflow per-node artifact.json 污染 envelope。
    """
    work_dir = Path(work_dir)
    verify = runner.artifacts.get("verify_artifact", {})
    summary = verify.get("summary", {})
    keep = runner.artifacts.get("_cleanup_keep")
    if keep is not None:
        report = str((work_dir / REPORT_FILE).resolve())
        artifacts = [p for p in keep if p != report and Path(p).exists()]
        artifacts = sorted(artifacts)
    else:
        artifacts = _artifact_paths_fallback(work_dir)
    return {
        "work_dir": str(work_dir),
        "report_path": str(Path(work_dir) / REPORT_FILE),
        "artifacts": artifacts,
        "verify": {
            "exit_code": summary.get("exit_code"),
            "envelope_ok": summary.get("envelope_ok"),
            "artifact_count": summary.get("artifact_count"),
        },
    }


def _run_with_envelope(coro_factory, started_at, *, build_data=None, on_after=None):
    """跑 flow + envelope,返回 (exit_code, break_kind, runner)。on_after 在 break 后调用。"""
    try:
        runner, break_kind, break_event = asyncio.run(coro_factory())
    except CliError as error:
        return _emit_error(error, started_at), "error", None
    except Exception as exc:
        return _emit_unexpected(exc, started_at), "error", None

    if break_kind == "error":
        try:
            raise break_event.as_exception()
        except CliError as error:
            return _emit_error(error, started_at), "error", None
        except Exception as exc:
            return _emit_unexpected(exc, started_at), "error", None

    exit_code, _ = Runner.to_envelope(break_kind, break_event)
    # 先清理再 emit:envelope 里只带清理后仍存在的路径(artifacts/report_path)
    if on_after:
        on_after(break_kind, runner)
    if break_kind == "end":
        _emit_envelope(True, data=build_data(runner) if build_data else None, started_at=started_at)
    return exit_code, break_kind, runner


def _gen_job_id():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=4))
    return f"{stamp}-{suffix}"


# —— 主流程 ——

def main():
    started_at = time.time()
    args = build_parser().parse_args()
    flow_dir = str(Path(__file__).parent)

    if args.schema:
        output_schema()
        return EXIT_OK

    if args.resume:
        job_dir = Path(args.resume).expanduser()
        if not job_dir.is_dir():
            print(f"job_dir 不存在:{job_dir}", file=sys.stderr)
            return EXIT_VALIDATION
        case = _load_case_from_job(job_dir)
        work_dir = job_dir
        node_args = _build_node_args(case, work_dir)

        def on_after(break_kind, runner):
            if break_kind in ("end", "error") and not args.keep:
                _cleanup_job(work_dir, runner)

        exit_code, _, _ = _run_with_envelope(
            lambda: _run_resume(flow_dir, job_dir, node_args),
            started_at, build_data=lambda r: _build_success_data(r, work_dir), on_after=on_after,
        )
        return exit_code

    # 首跑
    try:
        pass_check(_check_python3)
    except FlowCheckError as exc:
        print(f"预检失败:\n{exc}", file=sys.stderr)
        return EXIT_VALIDATION

    if not args.case:
        print("缺少用例位置参数,用 --schema 查看契约", file=sys.stderr)
        return EXIT_VALIDATION
    try:
        case = parse_case(args.case)
    except CliError as error:
        return _emit_error(error, started_at)

    work_dir = DEFAULT_WORK_ROOT / _gen_job_id()
    node_args = _build_node_args(case, work_dir)

    def on_after_first(break_kind, runner):
        # to_agent/end/error 都持久化 case 供 --resume
        _persist_case(work_dir, case)
        if break_kind in ("end", "error") and not args.keep:
            _cleanup_job(work_dir, runner)

    exit_code, _, _ = _run_with_envelope(
        lambda: _run_flow(flow_dir, DEFAULT_WORK_ROOT, work_dir, node_args),
        started_at, build_data=lambda r: _build_success_data(r, work_dir), on_after=on_after_first,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
