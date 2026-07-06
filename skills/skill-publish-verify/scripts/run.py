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


def _cleanup_job(work_dir):
    """end/error 后极简清理:只保留 skill 产物 + skill_verify_report.md。

    读 run_record.artifacts 取实际产物路径,保留其父目录链;另保留报告文件。
    work_dir 内其他条目(venv、skill 副本、brief、_case.json、esflow per-node
    目录、agent 临时日志、run_record.json、verify_facts.json、install_deps.log)
    全删。to_agent 中断时不调用——还要 --resume 跑后续节点。
    """
    work_dir = Path(work_dir)
    keep_files = {work_dir / REPORT_FILE}
    keep_dirs = set()
    record_path = work_dir / RUN_RECORD_FILE
    if record_path.is_file():
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            work_root = work_dir.resolve()
            for raw in record.get("artifacts") or []:
                p = Path(str(raw)).resolve()
                if not p.is_relative_to(work_root):
                    continue
                rel = p.relative_to(work_root).parts
                if len(rel) > 1:
                    keep_dirs.add(work_dir / rel[0])
                else:
                    keep_files.add(p)
        except (OSError, json.JSONDecodeError):
            pass
    for p in work_dir.iterdir():
        if p in keep_files or p in keep_dirs:
            continue
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except OSError:
                pass


def _artifact_paths(work_dir):
    """清理后扫 work_dir,返回除报告外的所有文件绝对路径(即 skill 产物)。

    清理已删 run_record.json,改用 rglob 扫描保留的产物。to_agent 中断时未清理,
    仍能扫到 out/ 等产物目录。
    """
    work_dir = Path(work_dir)
    paths = []
    for p in work_dir.rglob("*"):
        if p.is_file() and p.name != REPORT_FILE:
            paths.append(str(p.resolve()))
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
    """清理后构造 envelope.data:只带仍存在的路径。

    run_record.json / verify_facts.json 已被 _cleanup_job 删除,不再写入 envelope。
    artifacts 列表读 run_record 后给出实际存在的产物路径(清理后保留的)。
    """
    verify = runner.artifacts.get("verify_artifact", {})
    summary = verify.get("summary", {})
    return {
        "work_dir": str(work_dir),
        "report_path": str(Path(work_dir) / REPORT_FILE),
        "artifacts": _artifact_paths(work_dir),
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
                _cleanup_job(work_dir)

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
            _cleanup_job(work_dir)

    exit_code, _, _ = _run_with_envelope(
        lambda: _run_flow(flow_dir, DEFAULT_WORK_ROOT, work_dir, node_args),
        started_at, build_data=lambda r: _build_success_data(r, work_dir), on_after=on_after_first,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
