"""aggregate 节点:纯 Python 双索引聚合,从 review.json 算作者榜 + commit 明细。

LLM 任务在 agent_review 已完成,本节点是规则化计算:
- 按作者分组合并 commit,算 PN/最高风险/高风险数
- 作者榜 action 取该作者最高风险 commit 的 fix_suggestion(非第一条)
- 算各风险等级计数
- 输出 aggregate.json (机器读) + process.md (人读)
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_RUNTIME, RISK_ORDER, RISK_RANK, log, validate_review_json


def _make_pn(levels):
    chunks = []
    for risk in RISK_ORDER:
        count = levels.count(risk)
        if count:
            chunks.append(f"{risk}={count}")
    return " ".join(chunks) or "P5=0"


def _sort_level(levels):
    return sorted(levels, key=lambda item: RISK_RANK.get(item, 99))[0] if levels else "P5"


def _high_risk_count(levels):
    return sum(1 for level in levels if level in {"P1", "P2"})


def _aggregate(reviews, scope):
    """从 reviews 列表算双索引。作者榜 action 取该作者最高风险 commit 的 fix_suggestion。"""
    commits = []
    grouped = defaultdict(list)
    for review in reviews:
        item = {
            "author": review["author"],
            "hash": review["hash"],
            "time": review.get("time", ""),
            "level": review["risk_level"],
            "summary": review["risk_summary"],
            "files": review["files"],
            "test": review["fix_suggestion"],
        }
        commits.append(item)
        grouped[review["author"]].append(item)

    authors = []
    for author, rows in grouped.items():
        levels = [row["level"] for row in rows]
        # 按 risk_rank 升序取最高风险那条的 fix_suggestion 作为 action
        top_row = min(rows, key=lambda r: RISK_RANK.get(r["level"], 99))
        authors.append({
            "author": author,
            "count": len(rows),
            "pn": _make_pn(levels),
            "maxRisk": _sort_level(levels),
            "highRiskCount": _high_risk_count(levels),
            "summary": "；".join(row["summary"] for row in rows[:2]),
            "action": top_row["test"],
        })
    authors.sort(key=lambda row: (RISK_RANK.get(row["maxRisk"], 99), -row["highRiskCount"], row["author"]))

    counts = {risk: 0 for risk in RISK_ORDER}
    for commit in commits:
        counts[commit["level"]] = counts.get(commit["level"], 0) + 1

    return {
        "scope": scope,
        "authors": authors,
        "commits": commits,
        "counts": counts,
        "total": len(commits),
        "maxRisk": _sort_level([c["level"] for c in commits]),
    }


def _render_process_md(data, reviews):
    """人读的 process.md:审查记录 + 双索引聚合表。"""
    lines = [f"# Git Review 过程记录", "", f"审查范围：{data['scope']}，排除 merge commit。共 {data['total']} 个提交。", ""]

    lines.append("## 审查记录")
    lines.append("")
    lines.append("| 提交者 | CommitHash | 时间 | 修改描述 | 存在什么风险 | 哪部分代码 | 造成风险原因 | 修改建议 | 风险等级 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in reviews:
        files = "<br>".join(r["files"])
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["author"], r["hash"], r.get("time", ""), r.get("subject", ""),
            r["risk_summary"], files, r.get("cause", ""), r["fix_suggestion"], r["risk_level"],
        ))
    lines.append("")

    lines.append("## 双索引聚合")
    lines.append("")
    lines.append("### A. 作者风险榜")
    lines.append("")
    lines.append("| 作者 | 提交数 | PN | 最高风险 | 高风险 commit 数 | 作者风险摘要 | 优先通知动作 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for a in data["authors"]:
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            a["author"], a["count"], a["pn"], a["maxRisk"], a["highRiskCount"], a["summary"], a["action"],
        ))
    lines.append("")

    lines.append("### B. Commit 风险明细")
    lines.append("")
    lines.append("| 作者 | CommitHash | 时间 | 风险等级 | 风险摘要 | 关键文件范围 | 必验项 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for c in data["commits"]:
        files = "<br>".join(c["files"])
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            c["author"], c["hash"], c["time"], c["level"], c["summary"], files, c["test"],
        ))
    lines.append("")
    return "\n".join(lines)


class Aggregate(Node):
    id = "aggregate"
    title = "双索引聚合"

    def run(self, ctx) -> dict:
        resolve = ctx.get("resolve")
        work_dir = Path(resolve["work_dir"])
        review_path = work_dir / "review.json"
        if not review_path.exists():
            raise CliError("aggregate_error", f"缺少 review.json:{review_path}", EXIT_RUNTIME)

        review_data = json.loads(review_path.read_text(encoding="utf-8"))
        ok, errors = validate_review_json(review_data)
        if not ok:
            raise CliError("aggregate_error", "review.json 不合规:" + "; ".join(errors), EXIT_RUNTIME)

        reviews = review_data["reviews"]
        data = _aggregate(reviews, resolve["scope"])
        aggregate_path = work_dir / "aggregate.json"
        aggregate_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        process_md = _render_process_md(data, reviews)
        process_path = work_dir / "process.md"
        process_path.write_text(process_md, encoding="utf-8")

        log(f"[aggregate] {data['total']} commits, authors={len(data['authors'])} -> {aggregate_path}")
        return {
            "aggregate_path": str(aggregate_path),
            "process_path": str(process_path),
            "total": data["total"],
            "max_risk": data["maxRisk"],
        }

    def deliver(self, artifact) -> bool:
        return Path(artifact["aggregate_path"]).exists() and Path(artifact["process_path"]).exists()
