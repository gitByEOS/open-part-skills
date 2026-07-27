"""结构化 Agent 摘要校验与最终 Markdown 渲染。"""

from __future__ import annotations

import json
import re
from collections import Counter
from html import escape
from pathlib import Path

from common import Request
from history import read_messages

CATEGORY_SPECS = (
    ("goals", "目标与请求"),
    ("constraints", "约束与偏好"),
    ("decisions", "决策与待办"),
    ("acceptance", "验收与验证"),
    ("blockers", "阻塞与未知"),
)
ACTION_STATUS_LABELS = {
    "pending": "待推进",
    "blocked": "受阻",
    "confirmed": "已确认",
}
ACTION_STATUS_ORDER = ("pending", "blocked", "confirmed")
MIN_HIGHLIGHTS_BY_MESSAGE_COUNT = (
    (20, 5),
    (5, 3),
    (1, 1),
)
MAX_ITEM_LENGTH = 500
MAX_QUOTE_LENGTH = 120


class SummaryValidationError(ValueError):
    """Agent 摘要未满足可追溯契约。"""


def empty_summary(request: Request) -> dict:
    return {
        "periods": [
            {"period": key, **{name: [] for name, _ in CATEGORY_SPECS}}
            for key in request.period_keys
        ],
        "period_highlights": [
            {"period": key, "items": []}
            for key in request.period_keys
        ],
        "action_items": [],
        "recurring_topics": [],
    }


def _require_keys(value: dict, expected: set[str], context: str) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        raise SummaryValidationError(f"{context} 字段错误：缺少={missing}，未知={unknown}")


def _message_index(messages: list[dict]) -> dict[str, dict]:
    index = {}
    for message in messages:
        evidence = message.get("evidence")
        if not evidence or evidence in index:
            raise SummaryValidationError(f"消息证据重复或为空：{evidence}")
        index[evidence] = message
    return index


def _validate_item(item, *, context: str, evidence_index: dict, period: str | None = None) -> dict:
    if not isinstance(item, dict):
        raise SummaryValidationError(f"{context} 必须是对象")
    _require_keys(item, {"text", "evidence"}, context)
    text = item["text"]
    evidence = item["evidence"]
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_ITEM_LENGTH:
        raise SummaryValidationError(f"{context}.text 为空或超过 {MAX_ITEM_LENGTH} 字")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(ref, str) for ref in evidence):
        raise SummaryValidationError(f"{context}.evidence 必须是非空字符串数组")
    if len(evidence) != len(set(evidence)):
        raise SummaryValidationError(f"{context}.evidence 不可重复")
    unknown = [ref for ref in evidence if ref not in evidence_index]
    if unknown:
        raise SummaryValidationError(f"{context} 引用了未知证据：{unknown}")
    if period is not None:
        cross_period = [ref for ref in evidence if evidence_index[ref]["period"] != period]
        if cross_period:
            raise SummaryValidationError(f"{context} 引用了其他周期证据：{cross_period}")
    for ref in evidence:
        raw = evidence_index[ref]["text"].strip()
        if len(raw) > MAX_QUOTE_LENGTH and raw in text:
            raise SummaryValidationError(f"{context} 复制了完整长原文：{ref}")
    return {"text": text.strip(), "evidence": evidence}


def _minimum_highlight_count(message_count: int) -> int:
    for threshold, minimum in MIN_HIGHLIGHTS_BY_MESSAGE_COUNT:
        if message_count >= threshold:
            return minimum
    return 0


def _validate_period_highlights(
    highlights,
    *,
    evidence_index: dict,
    request: Request,
    period_counts: dict,
) -> list[dict]:
    if not isinstance(highlights, list):
        raise SummaryValidationError("period_highlights 必须是数组")
    if [item.get("period") for item in highlights if isinstance(item, dict)] != list(request.period_keys):
        raise SummaryValidationError("period_highlights 必须按请求周期完整、有序输出")

    normalized = []
    for period_item in highlights:
        if not isinstance(period_item, dict):
            raise SummaryValidationError("period_highlights 元素必须是对象")
        _require_keys(period_item, {"period", "items"}, f"要点周期 {period_item.get('period')}")
        period = period_item["period"]
        items = period_item["items"]
        if not isinstance(items, list):
            raise SummaryValidationError(f"要点周期 {period}.items 必须是数组")
        minimum = _minimum_highlight_count(period_counts.get(period, 0))
        if len(items) < minimum:
            raise SummaryValidationError(f"要点周期 {period} 至少需要 {minimum} 条本期要点")
        normalized.append({
            "period": period,
            "items": [
                _validate_item(
                    item,
                    context=f"要点周期 {period}.items[{index}]",
                    evidence_index=evidence_index,
                    period=period,
                )
                for index, item in enumerate(items)
            ],
        })
    return normalized


def _validate_action_items(items, *, evidence_index: dict) -> list[dict]:
    if not isinstance(items, list):
        raise SummaryValidationError("action_items 必须是数组")

    normalized = []
    for index, item in enumerate(items):
        context = f"action_items[{index}]"
        if not isinstance(item, dict):
            raise SummaryValidationError(f"{context} 必须是对象")
        _require_keys(item, {"text", "status", "evidence"}, context)
        status = item["status"]
        if status not in ACTION_STATUS_LABELS:
            raise SummaryValidationError(f"{context}.status 无效：{status}")
        normalized_item = _validate_item(
            {"text": item["text"], "evidence": item["evidence"]},
            context=context,
            evidence_index=evidence_index,
        )
        normalized_item["status"] = status
        normalized.append(normalized_item)
    return normalized


def validate_summary(summary: dict, messages: list[dict], request: Request) -> dict:
    """校验 schema、周期与每项证据，返回规范化摘要。"""
    if not isinstance(summary, dict):
        raise SummaryValidationError("summary.json 顶层必须是对象")
    _require_keys(summary, {"periods", "period_highlights", "action_items", "recurring_topics"}, "summary")
    evidence_index = _message_index(messages)
    periods = summary["periods"]
    if not isinstance(periods, list):
        raise SummaryValidationError("periods 必须是数组")
    if [item.get("period") for item in periods if isinstance(item, dict)] != list(request.period_keys):
        raise SummaryValidationError("periods 必须按请求周期完整、有序输出")

    normalized_periods = []
    expected_period_keys = {"period", *(name for name, _ in CATEGORY_SPECS)}
    for period_item in periods:
        if not isinstance(period_item, dict):
            raise SummaryValidationError("periods 元素必须是对象")
        _require_keys(period_item, expected_period_keys, f"周期 {period_item.get('period')}")
        period = period_item["period"]
        normalized = {"period": period}
        for category, _ in CATEGORY_SPECS:
            items = period_item[category]
            if not isinstance(items, list):
                raise SummaryValidationError(f"周期 {period}.{category} 必须是数组")
            normalized[category] = [
                _validate_item(
                    item,
                    context=f"周期 {period}.{category}[{index}]",
                    evidence_index=evidence_index,
                    period=period,
                )
                for index, item in enumerate(items)
            ]
        normalized_periods.append(normalized)

    highlights = _validate_period_highlights(
        summary["period_highlights"],
        evidence_index=evidence_index,
        request=request,
        period_counts=Counter(message["period"] for message in messages),
    )
    action_items = _validate_action_items(summary["action_items"], evidence_index=evidence_index)

    topics = summary["recurring_topics"]
    if not isinstance(topics, list):
        raise SummaryValidationError("recurring_topics 必须是数组")
    normalized_topics = []
    for index, topic in enumerate(topics):
        context = f"recurring_topics[{index}]"
        normalized = _validate_item(topic, context=context, evidence_index=evidence_index)
        periods_seen = sorted({evidence_index[ref]["period"] for ref in normalized["evidence"]})
        if len(normalized["evidence"]) < 2 or len(periods_seen) < 2:
            raise SummaryValidationError(f"{context} 至少需要跨两个周期的两条证据")
        normalized["periods"] = periods_seen
        normalized["message_count"] = len(normalized["evidence"])
        normalized_topics.append(normalized)

    return {
        "periods": normalized_periods,
        "period_highlights": highlights,
        "action_items": action_items,
        "recurring_topics": normalized_topics,
    }


def _evidence_text(item: dict) -> str:
    return "、".join(f"`{ref}`" for ref in item["evidence"])


def _period_themes(period_item: dict) -> str:
    values = []
    for category, _ in CATEGORY_SPECS:
        values.extend(item["text"] for item in period_item[category])
    return "；".join(values[:3]) if values else "无明确主题"


def _table_cell(value: str) -> str:
    """将原文放入 Markdown 表格单元格，同时保留可读内容。"""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return escape(value, quote=False).replace("|", "&#124;").replace("\n", "<br>")


def render_messages_table(collection: dict) -> str:
    """按消息时间升序输出用户发言原文表。"""
    messages = read_messages(Path(collection["messages_path"]))
    messages.sort(key=lambda message: (message.get("timestamp", ""), message.get("evidence", "")))
    lines = [
        "# 用户发言",
        "",
        "| 时间 | 内容 |",
        "| --- | --- |",
    ]
    if not messages:
        lines.append("| - | 无匹配 user 发言 |")
    for message in messages:
        lines.append(f"| {_table_cell(str(message.get('timestamp', '')))} | {_table_cell(str(message.get('text', '')))} |")
    return "\n".join(lines) + "\n"


def render_report(request: Request, collection: dict, summary: dict) -> str:
    stats = Counter(collection.get("stats") or {})
    time_sources = Counter(collection.get("time_sources") or {})
    period_counts = collection.get("period_counts") or {}
    active_sources = collection.get("active_sources") or {}
    included = stats["included"]
    source_types = ", ".join(request.sources) if request.sources else "自定义目录（自动识别已知 schema）"
    command_display = re.sub(
        r"--dir\s+\S+",
        f"--dir <{request.custom_source_label or 'custom'}>",
        request.command,
    )

    lines = [
        "# 用户发言汇总",
        "",
        "## 范围",
        f"- 命令：`{command_display}`",
        f"- 时区与生成时刻：`{request.timezone}`；`{request.now}`",
        f"- 窗口：`[{request.window_start}, {request.window_end})`",
        "- 时间源策略：消息 timestamp 优先；源 JSONL mtime fallback",
        f"- 数据范围：{source_types}；只读已识别 user 记录，不含 assistant/system/developer/tool",
        "- 身份限制：`user` 仅为源记录角色声明，不证明真实发言者身份",
        "",
        "## 覆盖与完整性",
        f"- 扫描文件：{stats['files_scanned']}（发现 {collection.get('discovery', {}).get('files_discovered', stats['files_scanned'])}）",
        f"- 有效 JSON：{stats['valid_json']}；JSON 解析错误：{stats['json_parse_errors']}",
        f"- `role: user` / 已识别用户记录：{stats['user_records']}；纳入：{included}",
        f"- 时间源：精确消息时间 {time_sources['message_timestamp']}；文件 mtime fallback {time_sources['file_mtime_fallback']}；时间解析失败 {stats['timestamp_parse_failed']}",
        f"- 跳过：空文本 {stats['empty_text']}；窗口外 {stats['outside_window']}；未知或非 user schema {stats['non_user_or_unknown']}；重复 {stats['duplicates_skipped']}",
        "",
        "## 周期总览",
        "| 周期 | 消息数 | 活跃源文件 | 主要主题 |",
        "| --- | ---: | ---: | --- |",
    ]
    summary_by_period = {item["period"]: item for item in summary["periods"]}
    highlights_by_period = {item["period"]: item["items"] for item in summary["period_highlights"]}
    for key in request.period_keys:
        themes = highlights_by_period[key] or [
            {"text": _period_themes(summary_by_period[key])}
        ]
        lines.append(
            f"| {key} | {period_counts.get(key, 0)} | {active_sources.get(key, 0)} | "
            f"{'；'.join(item['text'] for item in themes[:3])} |"
        )

    lines.extend(["", "## 本期要点"])
    for key in request.period_keys:
        items = highlights_by_period[key]
        lines.extend(["", f"### {key}"])
        if not items:
            lines.append("- 无明确要点")
            continue
        for item in items:
            lines.append(f"- {item['text']}；依据：{_evidence_text(item)}")

    lines.extend(["", "## 关键决策与待办"])
    if not summary["action_items"]:
        lines.append("- 无明确待跟进事项")
    else:
        for status in ACTION_STATUS_ORDER:
            status_items = [item for item in summary["action_items"] if item["status"] == status]
            if not status_items:
                continue
            lines.append(f"- {ACTION_STATUS_LABELS[status]}：")
            for item in status_items:
                lines.append(f"  - {item['text']}；依据：{_evidence_text(item)}")

    lines.extend(["", "## 分周期摘要"])
    if not included:
        lines.extend(["", "无匹配 user 发言"])
    for key in request.period_keys:
        period_item = summary_by_period[key]
        lines.extend(["", f"### {key}"])
        for category, title in CATEGORY_SPECS:
            items = period_item[category]
            if not items:
                lines.append(f"- {title}：无")
                continue
            lines.append(f"- {title}：")
            for item in items:
                lines.append(f"  - {item['text']}；依据：{_evidence_text(item)}")

    lines.extend(["", "## 反复主题"])
    if not summary["recurring_topics"]:
        lines.append("- 无满足跨周期证据要求的反复主题")
    for topic in summary["recurring_topics"]:
        periods = "、".join(topic["periods"])
        lines.append(f"- {topic['text']}：出现于 {periods}；消息数 {topic['message_count']}；依据：{_evidence_text(topic)}")

    lines.extend([
        "",
        "## 用户发言原文产物",
        f"- 路径：`{request.original_path}`",
        "- 内容：按时间升序排列的 `| 时间 | 内容 |` 用户发言表",
        "- 不含：真实绝对源路径、assistant/system/developer/tool 内容",
    ])
    return "\n".join(lines) + "\n"


def load_and_validate_summary(summary_path: Path, messages_path: Path, request: Request) -> tuple[dict, list[dict]]:
    messages = read_messages(messages_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return validate_summary(summary, messages, request), messages
