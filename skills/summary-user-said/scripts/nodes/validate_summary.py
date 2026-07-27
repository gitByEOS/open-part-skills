"""validate_summary 节点：验证统计不变量与 Agent 摘要证据。"""

from __future__ import annotations

from pathlib import Path

from esflow import Node

from common import SUMMARY_FILENAME, request_from_dict
from history import read_messages
from report import empty_summary, load_and_validate_summary, validate_summary


class ValidateSummary(Node):
    id = "validate_summary"
    title = "校验摘要与证据"

    def run(self, ctx) -> dict:
        collection = ctx.get("collect_messages")
        request = request_from_dict(collection["request"])
        messages_path = Path(collection["messages_path"])
        messages = read_messages(messages_path)
        included = collection.get("stats", {}).get("included", 0)
        period_sum = sum(collection.get("period_counts", {}).values())
        unique = collection.get("unique_message_ids", 0)
        if not (len(messages) == included == period_sum == unique):
            raise ValueError(
                "消息计数不守恒："
                f"lines={len(messages)}, included={included}, period_sum={period_sum}, unique={unique}"
            )

        agent_artifact = ctx.get("agent_summary")
        if included == 0:
            summary = validate_summary(empty_summary(request), messages, request)
        else:
            if not agent_artifact:
                raise ValueError("有匹配消息但缺少 Agent 摘要产物")
            summary_path = Path(agent_artifact["output_dir"]) / SUMMARY_FILENAME
            summary, _ = load_and_validate_summary(summary_path, messages_path, request)

        return {
            "summary": summary,
            "validated_messages": len(messages),
            "evidence_count": len({message["evidence"] for message in messages}),
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("validated_messages") is not None)
