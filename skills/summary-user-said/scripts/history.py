"""会话历史适配、时间提取与流式 JSONL 收集。"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from common import Request, parse_iso_datetime, period_key

_TIMESTAMP_TAG = re.compile(r"<timestamp>(.*?)</timestamp>", re.IGNORECASE | re.DOTALL)
_USER_QUERY_TAG = re.compile(r"<user_query>(.*?)</user_query>", re.IGNORECASE | re.DOTALL)
_UTC_OFFSET = re.compile(r"\(UTC\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?\)", re.IGNORECASE)
_BLOCK_TAGS = (
    "system-reminder",
    "manually_attached_skills",
    "attached_files",
    "image_files",
    "teammate-message",
    "task-notification",
    "local-command-caveat",
    "local-command-stdout",
)
_CURSOR_AUTOMATED_MESSAGES = frozenset({
    "briefly inform the user about the task result and perform any follow-up actions (if needed).",
    "the above subagent result is already visible to the user. do not reiterate or summarize its contents unless asked, or if multi-task result synthesis is required. otherwise do not say anything and end your turn.",
})
_CLAUDE_AUTOMATED_PREFIXES = (
    "another claude session sent a message:",
    "this session is being continued from a previous conversation that ran out of context.",
)
_CLAUDE_INTERRUPTION = re.compile(r"^\[request interrupted by user(?: for tool use)?\]$", re.IGNORECASE)
_CODEX_INJECTED_SECTION_MARKERS = (
    "\n\nQQ 文件回传规则：",
    "\n\n产物目录规则：",
    "\n\n执行环境说明：",
    "\n\n网关托管规则：",
    "\n\n待办提醒规则：",
    "\n\n浏览器工具规则：",
)
_CODEX_DELEGATION_HEADER = re.compile(
    r"^你是\s*(?:developer|analyst|tester(?:[-\w]*)?|reviewer|researcher)\s*[，,](?:任务|职责)\s*[：:]",
    re.IGNORECASE,
)
_CODEX_DELEGATION_MARKERS = (
    "协作要求：",
    "【汇报路径硬约束】",
    "你的 sessid 是 codex 本次 session id",
    "完成后向本目录 message.md",
)
_CODEX_CURRENT_REQUEST = re.compile(r"(?:^|\n\n)用户当前请求：\s*(.*)$", re.DOTALL)
_CODEX_TEAM_MEMBER = re.compile(r"(?:\.codex-team|(?:\b|=)team[\w-]*)", re.IGNORECASE)


@dataclass(frozen=True)
class SourceFile:
    source_id: str
    source_type: str
    root_label: str
    path: Path
    relative_path: str


@dataclass(frozen=True)
class Candidate:
    text: str
    structured_time: str | None
    source_type: str


def discover_source_files(request: Request) -> tuple[list[SourceFile], dict]:
    """仅发现授权根目录下的常规 JSONL，且不跟随符号链接。"""
    roots: list[tuple[str, Path, str]] = []
    if request.custom_dir:
        roots.append(("auto", Path(request.custom_dir), request.custom_source_label or "custom"))
    else:
        from common import SOURCE_ROOTS

        roots.extend((source, SOURCE_ROOTS[source], source) for source in request.sources)

    found: list[tuple[str, str, Path, str]] = []
    missing_roots = []
    authorized_roots = []
    skipped_symlinks = 0
    for source_type, configured_root, root_label in roots:
        try:
            root = configured_root.expanduser().resolve(strict=True)
        except OSError:
            missing_roots.append(root_label)
            continue
        if not root.is_dir():
            missing_roots.append(root_label)
            continue
        authorized_roots.append({"label": root_label, "source_type": source_type})
        for path in root.rglob("*.jsonl"):
            try:
                if path.is_symlink():
                    skipped_symlinks += 1
                    continue
                resolved_path = path.resolve(strict=True)
                relative = resolved_path.relative_to(root).as_posix()
                if not resolved_path.is_file():
                    continue
            except (OSError, ValueError):
                skipped_symlinks += 1
                continue
            found.append((root_label, relative, resolved_path, source_type))

    found.sort(key=lambda item: (item[0], item[1]))
    files = [
        SourceFile(
            source_id=f"source-{index:03d}",
            source_type=source_type,
            root_label=root_label,
            path=path,
            relative_path=relative,
        )
        for index, (root_label, relative, path, source_type) in enumerate(found, 1)
    ]
    return files, {
        "roots_requested": len(roots),
        "roots_authorized": authorized_roots,
        "roots_missing": missing_roots,
        "files_discovered": len(files),
        "symlinks_skipped": skipped_symlinks,
    }


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") not in {"text", "input_text"}:
            continue
        text = item.get("text")
        if isinstance(text, str):
            texts.append(text)
    return "\n".join(texts)


def _cursor_candidate(record: dict) -> Candidate | None:
    if record.get("role") != "user" or not isinstance(record.get("message"), dict):
        return None
    text = _content_text(record["message"].get("content"))
    return Candidate(text, None, "cursor") if text else Candidate("", None, "cursor")


def _claude_candidate(record: dict) -> Candidate | None:
    message = record.get("message")
    if record.get("type") != "user" or not isinstance(message, dict) or message.get("role") != "user":
        return None
    return Candidate(_content_text(message.get("content")), record.get("timestamp"), "claude")


def _codex_event_candidate(record: dict) -> Candidate | None:
    payload = record.get("payload")
    if record.get("type") != "event_msg" or not isinstance(payload, dict) or payload.get("type") != "user_message":
        return None
    text = payload.get("message")
    return Candidate(text if isinstance(text, str) else "", record.get("timestamp"), "codex")


def _codex_response_candidate(record: dict) -> Candidate | None:
    payload = record.get("payload")
    if record.get("type") != "response_item" or not isinstance(payload, dict):
        return None
    if payload.get("type") != "message" or payload.get("role") != "user":
        return None
    return Candidate(_content_text(payload.get("content")), record.get("timestamp"), "codex")


def detect_candidate(record: dict, source_type: str, *, allow_codex_response=True) -> Candidate | None:
    """按指定适配器提取候选；auto 仅接受可证实的已知结构。"""
    if source_type == "cursor":
        return _cursor_candidate(record)
    if source_type == "claude":
        return _claude_candidate(record)
    if source_type == "codex":
        return _codex_event_candidate(record) or (_codex_response_candidate(record) if allow_codex_response else None)
    return (
        _cursor_candidate(record)
        or _claude_candidate(record)
        or _codex_event_candidate(record)
        or (_codex_response_candidate(record) if allow_codex_response else None)
    )


def _strip_block(text: str, tag: str) -> str:
    return re.sub(rf"<{tag}(?:\s[^>]*)?>.*?</{tag}>", "", text, flags=re.IGNORECASE | re.DOTALL)


def normalize_user_text(text: str, source_type: str | None = None) -> str:
    """优先取显式 user_query，再移除时间与已知 harness 注入块。"""
    queries = [part.strip() for part in _USER_QUERY_TAG.findall(text) if part.strip()]
    value = "\n\n".join(queries) if queries else text
    value = _TIMESTAMP_TAG.sub("", value)
    for tag in _BLOCK_TAGS:
        value = _strip_block(value, tag)
    if source_type == "codex":
        injected_positions = [value.find(marker) for marker in _CODEX_INJECTED_SECTION_MARKERS if marker in value]
        if injected_positions:
            value = value[:min(injected_positions)]
        current_request = _CODEX_CURRENT_REQUEST.search(value)
        if current_request:
            value = current_request.group(1)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def is_cursor_automated_message(text: str) -> bool:
    """识别 Cursor 以 user 角色写入、但并非用户发言的固定收尾提示。"""
    return " ".join(text.lower().split()) in _CURSOR_AUTOMATED_MESSAGES


def is_claude_automated_message(text: str) -> bool:
    """识别 Claude 写入 user 记录的跨会话与中断事件。"""
    normalized = " ".join(text.lower().split())
    return normalized.startswith(_CLAUDE_AUTOMATED_PREFIXES) or bool(_CLAUDE_INTERRUPTION.fullmatch(normalized))


def is_codex_delegation(text: str) -> bool:
    """识别团队调度器转发给 Codex Agent 的委派任务。"""
    return (
        bool(_CODEX_DELEGATION_HEADER.match(text))
        or any(marker in text for marker in _CODEX_DELEGATION_MARKERS)
        or bool(_CODEX_TEAM_MEMBER.search(text))
    )


def _parse_tag_time(text: str) -> tuple[datetime | None, bool]:
    match = _TIMESTAMP_TAG.search(text)
    if not match:
        return None, False
    raw = match.group(1).strip()

    def normalize_offset(offset):
        sign, hours, minutes = offset.group(1), int(offset.group(2)), int(offset.group(3) or 0)
        return f"{sign}{hours:02d}:{minutes:02d}"

    normalized = _UTC_OFFSET.sub(normalize_offset, raw)
    for pattern in ("%A, %b %d, %Y, %I:%M %p %z", "%a, %b %d, %Y, %I:%M %p %z"):
        try:
            return datetime.strptime(normalized, pattern), False
        except ValueError:
            continue
    return None, True


def _resolve_time(candidate: Candidate, file_mtime: datetime, local_tz) -> tuple[datetime, str, bool]:
    tagged, tag_failed = _parse_tag_time(candidate.text)
    if tagged is not None:
        return tagged.astimezone(local_tz), "message_timestamp", False
    if candidate.structured_time:
        try:
            return parse_iso_datetime(candidate.structured_time).astimezone(local_tz), "message_timestamp", tag_failed
        except (ValueError, TypeError):
            return file_mtime.astimezone(local_tz), "file_mtime_fallback", True
    return file_mtime.astimezone(local_tz), "file_mtime_fallback", tag_failed


def _file_has_codex_event(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _codex_event_candidate(record) is not None:
                    return True
    except OSError:
        return False
    return False


def collect_messages(files: Iterable[SourceFile], request: Request, output_path: Path) -> dict:
    """流式收集用户发言原文并写入节点级 JSONL。"""
    local_tz = ZoneInfo(request.timezone)
    window_start = parse_iso_datetime(request.window_start)
    window_end = parse_iso_datetime(request.window_end)
    stats: Counter[str] = Counter()
    time_sources: Counter[str] = Counter()
    period_counts: Counter[str] = Counter({key: 0 for key in request.period_keys})
    active_sources: dict[str, set[str]] = defaultdict(set)
    source_index = []
    seen_ids: set[str] = set()
    seen_cursor_events: set[str] = set()

    with output_path.open("x", encoding="utf-8") as output:
        for source in files:
            source_index.append({
                "source_id": source.source_id,
                "source_type": source.source_type,
                "root": source.root_label,
                "relative_path": source.relative_path,
            })
            stats["files_scanned"] += 1
            try:
                file_mtime = datetime.fromtimestamp(source.path.stat().st_mtime, local_tz)
            except OSError:
                stats["files_unreadable"] += 1
                continue
            allow_codex_response = not _file_has_codex_event(source.path) if source.source_type in {"codex", "auto"} else True
            try:
                handle = source.path.open(encoding="utf-8", errors="replace")
            except OSError:
                stats["files_unreadable"] += 1
                continue
            with handle:
                for line_number, line in enumerate(handle, 1):
                    stats["lines_total"] += 1
                    try:
                        record = json.loads(line)
                        stats["valid_json"] += 1
                    except json.JSONDecodeError:
                        stats["json_parse_errors"] += 1
                        continue
                    candidate = detect_candidate(record, source.source_type, allow_codex_response=allow_codex_response)
                    if candidate is None:
                        stats["non_user_or_unknown"] += 1
                        continue
                    stats["user_records"] += 1
                    normalized = normalize_user_text(candidate.text, candidate.source_type)
                    if not normalized:
                        stats["empty_text"] += 1
                        continue
                    if candidate.source_type == "cursor" and is_cursor_automated_message(normalized):
                        stats["cursor_automated_messages"] += 1
                        continue
                    if candidate.source_type == "claude" and is_claude_automated_message(normalized):
                        stats["claude_automated_messages"] += 1
                        continue
                    if candidate.source_type == "codex" and is_codex_delegation(normalized):
                        stats["codex_delegations"] += 1
                        continue
                    instant, time_source, parse_failed = _resolve_time(candidate, file_mtime, local_tz)
                    if parse_failed:
                        stats["timestamp_parse_failed"] += 1
                    if not (window_start <= instant < window_end):
                        stats["outside_window"] += 1
                        continue
                    period = period_key(request.period_kind, instant)
                    if period not in period_counts:
                        stats["outside_period_keys"] += 1
                        continue
                    if candidate.source_type == "cursor":
                        event_key = hashlib.sha256(
                            f"{source.path.stem}\0{instant.isoformat()}\0{normalized}".encode("utf-8")
                        ).hexdigest()
                        if event_key in seen_cursor_events:
                            stats["duplicates_skipped"] += 1
                            continue
                        seen_cursor_events.add(event_key)
                    evidence = f"{source.source_id}:{line_number}"
                    message_id = hashlib.sha256(f"{evidence}\0{normalized}".encode("utf-8")).hexdigest()[:16]
                    if message_id in seen_ids:
                        stats["duplicates_skipped"] += 1
                        continue
                    seen_ids.add(message_id)
                    item = {
                        "message_id": message_id,
                        "period": period,
                        "timestamp": instant.isoformat(),
                        "time_source": time_source,
                        "evidence": evidence,
                        "source_type": candidate.source_type,
                        "content_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                        "text": normalized,
                    }
                    output.write(json.dumps(item, ensure_ascii=False) + "\n")
                    stats["included"] += 1
                    time_sources[time_source] += 1
                    period_counts[period] += 1
                    active_sources[period].add(source.source_id)

    return {
        "messages_path": str(output_path),
        "stats": dict(stats),
        "time_sources": dict(time_sources),
        "period_counts": dict(period_counts),
        "active_sources": {key: len(active_sources[key]) for key in request.period_keys},
        "source_index": source_index,
        "unique_message_ids": len(seen_ids),
    }


def read_messages(path: Path) -> list[dict]:
    messages = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                messages.append(json.loads(line))
    return messages
