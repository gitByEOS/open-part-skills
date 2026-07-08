"""verify_artifact 节点:读 run_record,全量事实外置 + 摘要进 artifact。

事实全量写 work_dir/verify_facts.json(供 agent_report 节点读)。
节点 artifact 只存摘要(facts_path + exit_code + envelope_ok + artifact_count),
避免最终 envelope 被单次 stdout/stderr 撑爆。

不依赖用例 expect,不做 pass/fail 判定。判断交给 agent_report 与用户。
"""

from __future__ import annotations

import json
from pathlib import Path

from esflow import Node

from common import RUN_RECORD_FILE, VERIFY_FACTS_FILE, log


_TEXT_HEAD_LIMIT = 2000


def _extract_envelope(record):
    """run_record.envelope 优先,否则从 steps 各步 stdout 末行 JSON 解析。"""
    if isinstance(record.get("envelope"), dict):
        return record["envelope"]
    steps = record.get("steps") or []
    for step in reversed(steps):
        stdout = step.get("stdout", "") or ""
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _read_text_head(path):
    """读文本文件前 N 字符,二进制或读失败返回 null。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(text) > _TEXT_HEAD_LIMIT:
        return text[:_TEXT_HEAD_LIMIT] + "\n...[truncated]"
    return text


def _collect_artifact_facts(artifacts):
    """对 run_record.artifacts 每个路径给存在性/大小/文本头部。"""
    facts = []
    for raw in artifacts or []:
        path = Path(str(raw))
        entry = {"path": str(path), "exists": path.exists()}
        if path.exists():
            try:
                entry["size"] = path.stat().st_size
            except OSError:
                entry["size"] = None
            if path.is_file():
                entry["text_head"] = _read_text_head(path)
        facts.append(entry)
    return facts


def _collect_work_dir_tree(work_dir):
    """work_dir 浅层条目概览,不递归(避免遍历 venv/skill 副本)。"""
    tree = []
    try:
        items = sorted(work_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return tree
    for p in items:
        entry = {"name": p.name, "type": "dir" if p.is_dir() else "file"}
        if p.is_file():
            try:
                entry["size"] = p.stat().st_size
            except OSError:
                entry["size"] = None
        tree.append(entry)
    return tree


class VerifyArtifact(Node):
    id = "verify_artifact"
    title = "收集验证事实"

    def run(self, ctx) -> dict:
        isolate = ctx.get("isolate_env")
        work_dir = Path(isolate["work_dir"])
        record = json.loads((work_dir / RUN_RECORD_FILE).read_text(encoding="utf-8"))
        envelope = _extract_envelope(record)
        steps = record.get("steps") or []
        last_exit = steps[-1].get("exit_code") if steps else None
        facts = {
            "run_record": {
                "steps": steps,
                "envelope": envelope,
            },
            "envelope_ok": bool(envelope and envelope.get("ok") is True),
            "artifacts": _collect_artifact_facts(record.get("artifacts")),
            "work_dir_tree": _collect_work_dir_tree(work_dir),
        }
        facts_path = work_dir / VERIFY_FACTS_FILE
        facts_path.write_text(
            json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")

        summary = {
            "facts_path": str(facts_path),
            "exit_code": last_exit,
            "envelope_ok": facts["envelope_ok"],
            "artifact_count": len(facts["artifacts"]),
        }
        log(f"[verify_artifact] facts -> {facts_path} "
            f"exit_code={summary['exit_code']} envelope_ok={summary['envelope_ok']} "
            f"artifacts={summary['artifact_count']}")
        return {"facts": facts, "summary": summary}

    def deliver(self, artifact) -> bool:
        if not artifact:
            return False
        summary = artifact.get("summary")
        return bool(summary and summary.get("facts_path"))
