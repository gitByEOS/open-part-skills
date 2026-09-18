"""meet-digest:发现运行时 → 解析 wav → 转写 → Agent 总结 → 落盘。"""

from esflow import edge, flow


@flow(id="meet-digest", title="会议转写提炼")
class MeetDigestFlow:
    nodes = [
        "resolve_runtime",
        "resolve_source",
        "transcribe",
        "agent_digest",
        "export_meet",
    ]
    edges = [
        edge("resolve_runtime", "resolve_source"),
        edge("resolve_source", "transcribe"),
        edge("transcribe", "agent_digest"),
        edge("agent_digest", "export_meet"),
    ]
