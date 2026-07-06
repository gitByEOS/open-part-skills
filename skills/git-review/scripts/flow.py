"""git-review flow:resolve → collect_commits → agent_review → aggregate → export_html。

agent_review 是 TO_AGENT 节点,跑到达它时框架退出(exit 2),
外部 Agent 读 assets/vigil.md + commits.json,写 review.json 后用 --resume 续跑。
"""

from esflow import flow, edge


@flow(id="git-review", title="git-review")
class GitReview:
    nodes = ["resolve", "collect_commits", "agent_review", "aggregate", "export_html"]
    edges = [
        edge("resolve", "collect_commits"),
        edge("collect_commits", "agent_review"),
        edge("agent_review", "aggregate"),
        edge("aggregate", "export_html"),
    ]
