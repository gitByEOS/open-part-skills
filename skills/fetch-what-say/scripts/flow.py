"""fetch-what-say flow:resolve → download → extract_audio → transcribe → agent_summary → export_html。

agent_summary 是 TO_AGENT 节点,跑到达它时框架退出(exit 2),
外部 Agent 写 summary.txt 后用 --resume 续跑 export_html。
--view 不进 flow,由 run.py 直接调用 nodes/export_html.generate_viewer。
"""

from esflow import flow, edge


@flow(id="fetch-what-say", title="fetch-what-say")
class FetchWhatSay:
    nodes = ["resolve", "download", "extract_audio", "transcribe",
             "agent_summary", "export_html"]
    edges = [
        edge("resolve", "download"),
        edge("download", "extract_audio"),
        edge("extract_audio", "transcribe"),
        edge("transcribe", "agent_summary"),
        edge("agent_summary", "export_html"),
    ]
