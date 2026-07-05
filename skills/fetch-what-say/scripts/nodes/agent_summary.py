"""agent_summary 节点:TO_AGENT checkpoint,产物 summary.txt 由外部 Agent 写入。

框架不调 run,就绪时调 accept:本节点在 accept 里把 self.output_dir 设为业务 work_dir,
框架尊重不覆盖,Agent 直接写 work_dir/summary.txt,export_html 无需 copy2 搬运。
然后 emit checkpoint 退出进程(exit 2)。

--resume 时框架扫 self.output_dir(work_dir)构造 artifact={"output_dir", "files"},
调 deliver 校验 summary.txt 存在,通过则转 DONE 跑下游。
"""

from pathlib import Path

from esflow import Node, Checkpoint


class AgentSummary(Node):
    id = "agent_summary"
    title = "Agent 写 summary"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        """设 output_dir 指向业务 work_dir,Agent 直接写业务目录,避免 export_html 再 copy。"""
        resolve = ctx.get("resolve")
        if resolve is None:
            return False
        self.output_dir = Path(resolve["work_dir"])
        return True

    def deliver(self, artifact) -> bool:
        """校验 Agent 写了 summary.txt 到 work_dir。"""
        return "summary.txt" in artifact.get("files", [])
