"""agent_report 节点:TO_AGENT,agent 写可用性报告。

accept 时把 verify_facts_path + 摘要 + SKILL.md 路径写到
work_dir/_agent_report_brief.json,设 output_dir=work_dir。agent 读 brief +
verify_facts.json + run_record.json + skill_dir/SKILL.md 写
work_dir/skill_verify_report.md,需含固定章节:可用性评分、卡壳点、文档问题、
产物结论、改进建议。deliver 校验报告存在、非空、且含全部必需章节标题。
"""

from __future__ import annotations

import json
from pathlib import Path

from esflow import Node, Checkpoint

from common import (
    AGENT_REPORT_BRIEF,
    REPORT_FILE,
    RUN_RECORD_FILE,
    VERIFY_FACTS_FILE,
    log,
)


REPORT_REQUIRED_SECTIONS = ["可用性评分", "卡壳点", "文档问题", "产物结论", "改进建议"]


class AgentReport(Node):
    id = "agent_report"
    title = "Agent 写可用性报告"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        isolate = ctx.get("isolate_env")
        copy_skill = ctx.get("copy_skill")
        agent_run = ctx.get("agent_run")
        verify = ctx.get("verify_artifact")
        if not isolate or not copy_skill or not agent_run or not verify:
            return False
        work_dir = Path(isolate["work_dir"])
        self.output_dir = work_dir
        summary = verify.get("summary", {})
        brief = {
            "work_dir": str(work_dir),
            "skill_dir": copy_skill["skill_dir"],
            "skill_md_path": str(Path(copy_skill["skill_dir"]) / "SKILL.md"),
            "run_record_path": str(work_dir / RUN_RECORD_FILE),
            "verify_facts_path": summary.get("facts_path") or str(work_dir / VERIFY_FACTS_FILE),
            "verify_summary": {
                "exit_code": summary.get("exit_code"),
                "envelope_ok": summary.get("envelope_ok"),
                "artifact_count": summary.get("artifact_count"),
            },
            "report_file": REPORT_FILE,
            "report_required_sections": REPORT_REQUIRED_SECTIONS,
            "resume_cmd": f"python3 scripts/run.py --resume {work_dir}",
        }
        (work_dir / AGENT_REPORT_BRIEF).write_text(
            json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[agent_report] brief -> {work_dir / AGENT_REPORT_BRIEF}")
        return True

    def deliver(self, artifact) -> bool:
        files = artifact.get("files", [])
        if REPORT_FILE not in files:
            return False
        output_dir = Path(artifact["output_dir"])
        try:
            content = (output_dir / REPORT_FILE).read_text(encoding="utf-8")
        except OSError:
            return False
        if not content.strip():
            return False
        missing = [s for s in REPORT_REQUIRED_SECTIONS if s not in content]
        return not missing
