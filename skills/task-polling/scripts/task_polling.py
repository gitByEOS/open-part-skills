#!/usr/bin/env python3
"""维护 docs/task.md 的单任务领取与完成流转"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

QUEUE_SECTION_NAMES = ("未领取", "进行中", "已完成")
STATIC_SECTION_NAMES = ("远期规划", "确认不做")
SECTION_NAMES = (*QUEUE_SECTION_NAMES, *STATIC_SECTION_NAMES)
TASK_PATTERN = re.compile(
    r"^- \[([ x])\] ([A-Za-z0-9][A-Za-z0-9_-]*)(?: \[([0-9a-f]{4,40})\])?\s*[:：]\s*(.+)$"
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
    complete.add_argument("--understanding", required=True, help="本轮任务理解")
    reopen = subparsers.add_parser("reopen", help="把已完成任务拿回进行中")
    reopen.add_argument("--id", required=True, help="已完成任务 ID")
    reopen.add_argument("--understanding", required=True, help="本轮任务理解")
    reopen.add_argument("--reason", required=True, help="未通过原因")
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
        title=match.group(4),
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


LEGACY_STATUS_PREFIXES = ("  - 完成结果：", "  - 返工原因：", "  - 验收打回：")
ROUND_LINE = re.compile(r"^  - 轮次(\d+)：(.*)$")
TASK_COMMIT = re.compile(r"^- \[[ x]\] [A-Za-z0-9][A-Za-z0-9_-]* \[([0-9a-f]{4,40})\]")
COMMIT_ID = re.compile(r"^[0-9a-f]{4,40}$")
DIRS_MARKER = re.compile(r"<dirs:(?:[A-Za-z0-9_./-]+;)*>")
DEV_ROOTS = {"docs", "src", "scripts"}
DEV_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".vue", ".css", ".scss", ".html", ".sh"}


def task_payload(task: Task) -> dict[str, object]:
    """返回任务标题及完整描述。"""
    return {
        "id": task.task_id,
        "title": task.title,
        "description": "\n".join(task.lines),
        "checked": task.checked,
    }


def single_clause(text: str, empty_message: str) -> str:
    """收成一行，分号只留给轮次分隔。"""
    collapsed = " ".join(text.split())
    if not collapsed:
        fail(empty_message)
    if "；" in collapsed or ";" in collapsed:
        fail("理解和未通过原因不能包含分号")
    return collapsed


def without_legacy_status(lines: tuple[str, ...]) -> list[str]:
    """去掉旧的完成结果、返工原因。"""
    return [line for line in lines if not line.startswith(LEGACY_STATUS_PREFIXES)]


def set_checkbox(line: str, checked: bool) -> str:
    marker = "x" if checked else " "
    updated, count = re.subn(r"^- \[[ x]\]", f"- [{marker}]", line, count=1)
    if count != 1:
        fail("任务首行缺少复选框")
    return updated


def latest_round(lines: list[str]) -> tuple[int, re.Match[str]] | None:
    found = [
        (index, match)
        for index, line in enumerate(lines)
        if (match := ROUND_LINE.match(line))
    ]
    if not found:
        return None
    return found[-1]


def git_text(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def status_path(line: str) -> str:
    payload = line[3:]
    if " -> " in payload:
        payload = payload.split(" -> ", 1)[1]
    if len(payload) >= 2 and payload.startswith('"') and payload.endswith('"'):
        payload = payload[1:-1]
    return payload


def repo_root(task_file: Path) -> Path:
    top = git_text(task_file.parent, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        fail("任务不在 git 仓库中，无法记录初始环境")
    return Path(top.stdout.strip())


def short_head(repo: Path) -> str:
    """读取初始环境的短 commit。"""
    head = git_text(repo, "log", "-1", "--abbrev-commit", "--format=%h", "HEAD")
    if head.returncode != 0:
        fail("仓库还没有 commit，无法记录初始环境")
    commit = head.stdout.strip()
    if not COMMIT_ID.fullmatch(commit):
        fail("无法解析初始环境 commit")
    return commit


def task_commit(line: str) -> str | None:
    match = TASK_COMMIT.match(line)
    if match is None:
        return None
    return match.group(1)


def stamp_initial_commit(line: str, commit: str) -> str:
    """初始环境只写一次，写在任务行。"""
    if task_commit(line):
        return line
    updated, count = re.subn(
        r"^(\- \[[ x]\] [A-Za-z0-9][A-Za-z0-9_-]*)",
        rf"\1 [{commit}]",
        line,
        count=1,
    )
    if count != 1:
        fail("任务首行无法写入初始环境")
    return updated


def is_dev_file(relative: str, task_path: Path, repo: Path) -> bool:
    """开发文档和源码。任务文档本身不算改动。"""
    path = Path(relative)
    if (repo / path).resolve() == task_path.resolve():
        return False
    if not path.parts:
        return False
    if path.parts[0] in DEV_ROOTS:
        return True
    return len(path.parts) == 1 and path.suffix.lower() in DEV_SUFFIXES


def format_dirs(names: list[str]) -> str:
    if not names:
        return "<dirs:>"
    return "<dirs:" + "".join(f"{name};" for name in names) + ">"


def pending_dev_dirs(repo: Path, task_path: Path) -> list[str]:
    """本轮待添加的开发文档和源码目录。"""
    status = git_text(repo, "status", "--porcelain")
    if status.returncode != 0:
        fail("无法读取工作区状态")
    names = {
        Path(relative).parts[0]
        for line in status.stdout.splitlines()
        if line.strip() and (relative := status_path(line)) and is_dev_file(relative, task_path, repo)
    }
    return sorted(names)


def add_dev_dirs(repo: Path, names: list[str]) -> None:
    if not names:
        return
    added = git_text(repo, "add", "-A", "--", *names)
    if added.returncode != 0:
        fail(f"无法添加改动目录：{added.stderr.strip()}")


def dirty_dev_files(repo: Path, names: list[str], task_path: Path) -> list[str]:
    """目录已 add 后，工作区里仍脏的开发文件。"""
    if not names:
        return []
    status = git_text(repo, "status", "--porcelain", "--", *names)
    if status.returncode != 0:
        fail("无法读取改动目录状态")
    dirty = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        relative = status_path(line)
        if (repo / relative).resolve() == task_path.resolve():
            continue
        if line.startswith("??") or len(line) < 2 or line[1] != " ":
            dirty.append(relative)
    return dirty


def previous_round(body: str) -> tuple[str, str]:
    """拆出上一轮的理解和改动目录。"""
    understanding, separator, rest = body.partition("；")
    if not separator:
        fail("上一轮没有改动目录")
    marker, _separator, _reason = rest.partition("；")
    if DIRS_MARKER.fullmatch(marker) is None:
        fail("上一轮没有改动目录")
    return understanding, marker


def write_round_understanding(lines: list[str], understanding: str, dirs: str) -> list[str]:
    """本轮写入理解和改动目录。未通过原因留在上一轮。"""
    current = latest_round(lines)
    if current is None:
        lines.append(f"  - 轮次1：{understanding}；{dirs}")
        return lines
    index, match = current
    lines[index] = f"  - 轮次{match.group(1)}：{understanding}；{dirs}"
    return lines


def reopen_next_round(lines: list[str], understanding: str, reason: str) -> list[str]:
    """未通过原因写到上一轮改动目录之后，再追加本轮理解。"""
    current = latest_round(lines)
    if current is None:
        fail("没有上一轮可写未通过原因")
    index, match = current
    previous_understanding, marker = previous_round(match.group(2))
    lines[index] = f"  - 轮次{match.group(1)}：{previous_understanding}；{marker}；{reason}"
    lines.append(f"  - 轮次{int(match.group(1)) + 1}：{understanding}")
    return lines


def with_checkbox(task: Task, checked: bool, lines: list[str]) -> Task:
    lines[0] = set_checkbox(lines[0], checked)
    return Task(task.task_id, task.title, checked, tuple(lines))


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
    commit = task_commit(task.lines[0]) or short_head(repo_root(path))
    claimed = Task(task.task_id, task.title, task.checked, tuple(
        [stamp_initial_commit(task.lines[0], commit), *task.lines[1:]]
    ))
    document.tasks["进行中"].append(claimed)
    atomic_write(path, render_document(document))
    return {"state": "claimed", "task": task_payload(claimed)}


def run_complete(path: Path, document: TaskDocument, task_id: str, understanding: str) -> dict[str, object]:
    understanding_text = single_clause(understanding, "任务理解不能为空")
    if not document.tasks["进行中"]:
        fail("没有可完成的进行中任务")

    task = document.tasks["进行中"][0]
    if task.task_id != task_id:
        fail(f"只能完成当前任务：{task.task_id}")

    repo = repo_root(path)
    body = without_legacy_status(task.lines)
    commit = task_commit(body[0]) or short_head(repo)
    body[0] = stamp_initial_commit(body[0], commit)
    names = pending_dev_dirs(repo, path.resolve())
    add_dev_dirs(repo, names)
    dirty = dirty_dev_files(repo, names, path.resolve())
    if dirty:
        shown = "、".join(dirty[:5])
        suffix = "等" if len(dirty) > 5 else ""
        fail(f"改动目录还没添加干净：{shown}{suffix}")
    body = write_round_understanding(body, understanding_text, format_dirs(names))
    completed_task = with_checkbox(task, True, body)
    document.tasks["进行中"].clear()
    document.tasks["已完成"].append(completed_task)
    atomic_write(path, render_document(document))
    return {"state": "completed", "task": task_payload(completed_task)}


def run_reopen(
    path: Path,
    document: TaskDocument,
    task_id: str,
    understanding: str,
    reason: str,
) -> dict[str, object]:
    understanding_text = single_clause(understanding, "任务理解不能为空")
    reason_text = single_clause(reason, "未通过原因不能为空")
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
    body = reopen_next_round(without_legacy_status(task.lines), understanding_text, reason_text)
    reopened_task = with_checkbox(task, False, body)
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
            result = run_complete(arguments.file, document, arguments.id, arguments.understanding)
        else:
            result = run_reopen(
                arguments.file,
                document,
                arguments.id,
                arguments.understanding,
                arguments.reason,
            )
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
