"""agent_digest：TO_AGENT，等外部按模板写 meet.md。"""
import json
from pathlib import Path

from esflow import Checkpoint, Node

from common import BRIEF_FILENAME, MEET_DRAFT


class AgentDigest(Node):
    id = "agent_digest"
    title = "Agent 写会议总结"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        transcribe = ctx.get("transcribe")
        job_dir = (self.kwargs or {}).get("job_dir")
        if not transcribe or not job_dir:
            return False
        self.output_dir = Path(job_dir) / self.id
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        brief = {
            "task": "根据转写原文写可追溯会议总结，禁止编造",
            "whole_path": transcribe["whole"],
            "srt_path": transcribe["srt"],
            "draft_path": str(out_dir / MEET_DRAFT),
            "meet_name": transcribe["meet_name"],
            "requirements": [
                "通读 whole_path 至最后一句",
                "章节名与顺序：会议主题、讨论问题、话题一…、待办与落地、风险与未决项",
                "每个话题含问题与痛点、造成原因、方案与建议",
                "方案和待办必须能在原文搜到，搜不到就删",
                "直接写 Markdown 到 draft_path，不包代码围栏",
            ],
        }
        (out_dir / BRIEF_FILENAME).write_text(
            json.dumps(brief, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def deliver(self, artifact) -> bool:
        if MEET_DRAFT not in artifact.get("files", []):
            return False
        path = Path(artifact["output_dir"]) / MEET_DRAFT
        return path.is_file() and len(path.read_text(encoding="utf-8").strip()) > 20
