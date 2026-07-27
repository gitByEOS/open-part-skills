"""summary-user-said：发现 → 收集 → Agent 摘要 → 校验 → 双产物导出。"""

from esflow import edge, flow


@flow(id="summary-user-said", title="用户发言汇总")
class SummaryUserSaidFlow:
    nodes = [
        "discover_sources",
        "collect_messages",
        "agent_summary",
        "validate_summary",
        "export_report",
    ]
    edges = [
        edge("discover_sources", "collect_messages"),
        edge("collect_messages", "agent_summary"),
        edge("agent_summary", "validate_summary"),
        edge("validate_summary", "export_report"),
    ]
