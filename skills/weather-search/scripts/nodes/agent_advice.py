"""agent_advice 节点:TO_AGENT checkpoint,等外部 agent 写出门防护建议。

不实现 run。框架就绪时 emit checkpoint 退出进程(exit 2),agent 读
job_dir/.esflow/analyze_grid/artifact.json 的 llm_text/llm_json,按样式写
advice.md 到本节点 output_dir,调 --resume 续跑,框架 deliver 校验后跑 export。

deliver 校验 advice.md 存在且非空。
"""

from pathlib import Path

from esflow import Checkpoint, Node

from weather_domain import ADVICE_FILENAME


class AgentAdvice(Node):
    id = "agent_advice"
    title = "Agent 写出门建议"
    checkpoint = Checkpoint.TO_AGENT

    def deliver(self, artifact) -> bool:
        files = artifact.get("files", [])
        if ADVICE_FILENAME not in files:
            return False
        out_dir = Path(artifact["output_dir"])
        content = (out_dir / ADVICE_FILENAME).read_text(encoding="utf-8").strip()
        return len(content) > 20
