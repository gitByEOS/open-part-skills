#!/usr/bin/env python3
"""维护 docs/task.md 的单任务领取与完成流转"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

QUEUE_SECTION_NAMES = ("未领取", "进行中", "已完成")
STATIC_SECTION_NAMES = ("远期规划", "确认不做")
SECTION_NAMES = (*QUEUE_SECTION_NAMES, *STATIC_SECTION_NAMES)
TASK_PATTERN = re.compile(
    r"^- \[([ x])\] ([A-Za-z0-9][A-Za-z0-9_-]*)\s*[:：]\s*(.+)$"
)
EMPTY_CHECKBOX_PATTERN = re.compile(r"^- \[ \](?:\s+无)?\s*$")


class TaskDocumentError(ValueError):
    """任务文档不符合约定格式"""


class TaskConflictError(TaskDocumentError):
    """任务操作与当前进行中任务冲突"""

    def __init__(self, message: str, task: Task):
        super().__init__(message)
        self.task = task


@dataclass(frozen=True)
class Task:
    """任务在文档中的完整块"""

    task_id: str
    title: str
    checked: bool
    lines: tuple[str, ...]


@dataclass
class TaskDocument:
    """任务文档的可流转区段与用户维护区段"""

    prefix_lines: tuple[str, ...]
    tasks: dict[str, list[Task]]
    static_sections: dict[str, tuple[str, ...]]


def fail(message: str) -> None:
    raise TaskDocumentError(message)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="维护 docs/task.md 的任务状态")
    parser.add_argument("--file", type=Path, default=Path("docs/task.md"), help="任务文档路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="读取当前任务状态")
    subparsers.add_parser("claim", help="领取首个未领取任务")
    complete = subparsers.add_parser("complete", help="完成当前进行中任务")
    complete.add_argument("--id", required=True, help="当前进行中任务 ID")
    complete.add_argument("--summary", required=True, help="完成结果摘要")
    reopen = subparsers.add_parser("reopen", help="验收失败，打回已完成任务")
    reopen.add_argument("--id", required=True, help="已完成任务 ID")
    reopen.add_argument("--reason", required=True, help="验收失败原因")
    return parser.parse_args()


def trim_boundary_blank_lines(lines: list[str]) -> tuple[str, ...]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while start < end and not lines[end - 1].strip():
        end -= 1
    return tuple(lines[start:end])


def split_sections(content: str) -> tuple[tuple[str, ...], dict[str, list[str]]]:
    lines = content.splitlines()
    if not lines or lines[0] != "# 任务计划":
        fail("首行必须是 # 任务计划")

    section_indexes: dict[str, int] = {}
    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        name = line[3:]
        if name in SECTION_NAMES:
            if name in section_indexes:
                fail(f"区段重复：{name}")
            section_indexes[name] = index

    missing_sections = [name for name in SECTION_NAMES if name not in section_indexes]
    if missing_sections:
        fail(f"缺少区段：{'、'.join(missing_sections)}")

    ordered_indexes = [section_indexes[name] for name in SECTION_NAMES]
    if ordered_indexes != sorted(ordered_indexes):
        fail("区段顺序必须为未领取、进行中、已完成、远期规划、确认不做")

    sections: dict[str, list[str]] = {}
    for index, name in enumerate(SECTION_NAMES):
        start = section_indexes[name] + 1
        end = section_indexes[SECTION_NAMES[index + 1]] if index + 1 < len(SECTION_NAMES) else len(lines)
        sections[name] = lines[start:end]
    return trim_boundary_blank_lines(lines[1 : section_indexes[SECTION_NAMES[0]]]), sections


def create_task(match: re.Match[str], lines: list[str]) -> Task:
    while lines and not lines[-1].strip():
        lines.pop()
    return Task(
        task_id=match.group(2),
        title=match.group(3),
        checked=match.group(1) == "x",
        lines=tuple(lines),
    )


def get_queue_tasks(lines: list[str], section_name: str) -> list[Task]:
    tasks: list[Task] = []
    current_lines: list[str] | None = None
    current_match: re.Match[str] | None = None

    for line in lines:
        match = TASK_PATTERN.match(line)
        if match:
            if current_match is not None and current_lines is not None:
                tasks.append(create_task(current_match, current_lines))
            current_match = match
            current_lines = [line]
            continue

        if EMPTY_CHECKBOX_PATTERN.fullmatch(line.strip()):
            continue

        if current_lines is None:
            if EMPTY_CHECKBOX_PATTERN.fullmatch(line.strip()):
                continue
            if line.strip():
                fail(f"{section_name} 存在任务外文本：{line}")
            continue

        if line.startswith(("  ", "\t")) or not line.strip():
            current_lines.append(line)
            continue
        fail(f"{section_name} 的任务内容必须缩进：{line}")

    if current_match is not None and current_lines is not None:
        tasks.append(create_task(current_match, current_lines))
    return tasks


def validate_document(content: str) -> TaskDocument:
    prefix_lines, sections = split_sections(content)
    tasks = {
        name: get_queue_tasks(sections[name], name)
        for name in QUEUE_SECTION_NAMES
    }
    task_ids = [task.task_id for section_tasks in tasks.values() for task in section_tasks]
    duplicate_ids = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
    if duplicate_ids:
        fail(f"任务 ID 重复：{'、'.join(duplicate_ids)}")

    for name in ("未领取", "进行中"):
        if any(task.checked for task in tasks[name]):
            fail(f"{name} 的任务必须使用 [ ]")
    if any(not task.checked for task in tasks["已完成"]):
        fail("已完成的任务必须使用 [x]")
    if len(tasks["进行中"]) > 1:
        fail("进行中最多只能有一个任务")

    return TaskDocument(
        prefix_lines=prefix_lines,
        tasks=tasks,
        static_sections={
            name: trim_boundary_blank_lines(sections[name])
            for name in STATIC_SECTION_NAMES
        },
    )


def render_document(document: TaskDocument) -> str:
    lines = ["# 任务计划", *document.prefix_lines]
    for name in SECTION_NAMES:
        lines.extend(("", f"## {name}"))
        if name in document.tasks:
            for task in document.tasks[name]:
                lines.extend(task.lines)
        else:
            lines.extend(document.static_sections[name])
    return "\n".join(lines).rstrip() + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        Path(temporary_path).unlink(missing_ok=True)
        raise


def read_document(path: Path) -> TaskDocument:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise TaskDocumentError(f"未找到任务文档：{path}") from error
    return validate_document(content)


def task_payload(task: Task) -> dict[str, object]:
    """返回任务标题及完整描述。"""
    return {
        "id": task.task_id,
        "title": task.title,
        "description": "\n".join(task.lines),
        "checked": task.checked,
    }


def print_result(result: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
        return
    print(result["state"])
    task = result.get("task")
    if isinstance(task, dict):
        print(f"{task['id']}：{task['title']}")


def run_status(document: TaskDocument) -> dict[str, object]:
    active_tasks = document.tasks["进行中"]
    pending_tasks = document.tasks["未领取"]
    if active_tasks:
        return {"state": "working", "task": task_payload(active_tasks[0])}
    if pending_tasks:
        return {"state": "pending", "task": task_payload(pending_tasks[0])}
    return {"state": "idle"}


def run_claim(path: Path, document: TaskDocument) -> dict[str, object]:
    if document.tasks["进行中"]:
        task = document.tasks["进行中"][0]
        raise TaskConflictError(f"已有进行中任务：{task.task_id}", task)
    if not document.tasks["未领取"]:
        return {"state": "idle"}

    task = document.tasks["未领取"].pop(0)
    document.tasks["进行中"].append(task)
    atomic_write(path, render_document(document))
    return {"state": "claimed", "task": task_payload(task)}


def run_complete(path: Path, document: TaskDocument, task_id: str, summary: str) -> dict[str, object]:
    if not summary.strip():
        fail("完成摘要不能为空")
    if not document.tasks["进行中"]:
        fail("没有可完成的进行中任务")

    task = document.tasks["进行中"][0]
    if task.task_id != task_id:
        fail(f"只能完成当前任务：{task.task_id}")

    completed_lines = list(task.lines)
    completed_lines[0] = completed_lines[0].replace("- [ ]", "- [x]", 1)
    completed_lines.append(f"  - 完成结果：{summary.strip()}")
    completed_task = Task(task.task_id, task.title, True, tuple(completed_lines))
    document.tasks["进行中"].clear()
    document.tasks["已完成"].append(completed_task)
    atomic_write(path, render_document(document))
    return {"state": "completed", "task": task_payload(completed_task)}


def run_reopen(path: Path, document: TaskDocument, task_id: str, reason: str) -> dict[str, object]:
    if not reason.strip():
        fail("验收打回原因不能为空")
    if document.tasks["进行中"]:
        fail(f"已有进行中任务：{document.tasks['进行中'][0].task_id}")

    completed_tasks = document.tasks["已完成"]
    task_index = next(
        (index for index, task in enumerate(completed_tasks) if task.task_id == task_id),
        None,
    )
    if task_index is None:
        fail(f"已完成中不存在任务：{task_id}")

    task = completed_tasks.pop(task_index)
    reopened_lines = list(task.lines)
    reopened_lines[0] = reopened_lines[0].replace("- [x]", "- [ ]", 1)
    reopened_lines.append(f"  - 验收打回：{reason.strip()}")
    reopened_task = Task(task.task_id, task.title, False, tuple(reopened_lines))
    document.tasks["进行中"].append(reopened_task)
    atomic_write(path, render_document(document))
    return {"state": "reopened", "task": task_payload(reopened_task)}


def main() -> int:
    arguments = get_arguments()
    try:
        document = read_document(arguments.file)
        if arguments.command == "status":
            result = run_status(document)
        elif arguments.command == "claim":
            result = run_claim(arguments.file, document)
        elif arguments.command == "complete":
            result = run_complete(arguments.file, document, arguments.id, arguments.summary)
        else:
            result = run_reopen(arguments.file, document, arguments.id, arguments.reason)
        print_result(result, arguments.json)
        return 0
    except TaskConflictError as error:
        if arguments.json:
            print(
                json.dumps(
                    {"state": "error", "error": str(error), "task": task_payload(error.task)},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    except TaskDocumentError as error:
        if arguments.json:
            print(json.dumps({"state": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
