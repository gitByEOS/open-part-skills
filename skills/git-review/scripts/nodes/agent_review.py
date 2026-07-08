"""agent_review 节点:TO_AGENT checkpoint,Agent 读 vigil.md + commits.json,
逐 commit 评估风险,写 review.json 到本节点 output_dir。

框架不调 run,accept 校验上游 resolve 就绪。
output_dir 由框架注入(默认 job_dir/agent_review/),Agent 直接写 review.json,
aggregate 与 export_html 从 artifact 拿 output_dir 拼路径,无需搬运。

--resume 时框架扫 output_dir 构造 artifact={output_dir, files},
deliver 校验 review.json 存在 + 结构合法 + 字段值类型合规。
deliver 失败时打印详细错误,Agent 能定位修复。
"""

from __future__ import annotations

import json
from pathlib import Path

from esflow import Node, Checkpoint

from common import log, validate_review_json


class AgentReview(Node):
    id = "agent_review"
    title = "Agent 写 review"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        return ctx.get("resolve") is not None

    def deliver(self, artifact) -> bool:
        """校验 Agent 写了合法的 review.json 到 output_dir,失败时打印详细原因。"""
        files = artifact.get("files", [])
        if "review.json" not in files:
            log("[agent_review] deliver 失败:output_dir 缺 review.json")
            return False
        try:
            data = json.loads(Path(self.output_dir, "review.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log(f"[agent_review] deliver 失败:review.json 解析失败:{exc}")
            return False
        ok, errors = validate_review_json(data)
        if not ok:
            log("[agent_review] deliver 失败:review.json 不合规:")
            for error in errors:
                log(f"  - {error}")
            return False
        return True
