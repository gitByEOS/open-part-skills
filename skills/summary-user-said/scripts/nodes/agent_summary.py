"""agent_summary 节点：有消息时等待 Agent 写结构化、可溯源摘要。"""

from __future__ import annotations

from pathlib import Path

from esflow import Checkpoint, Node

from common import BRIEF_FILENAME, SUMMARY_FILENAME, json_dump
from report import CATEGORY_SPECS


class AgentSummary(Node):
    id = "agent_summary"
    title = "Agent 生成可溯源摘要"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        collection = ctx.get("collect_messages")
        if not collection or collection.get("stats", {}).get("included", 0) == 0:
            return False
        request = collection["request"]
        job_dir = Path(collection["messages_path"]).parent.parent
        self.output_dir = job_dir / self.id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        brief = {
            "task": "只根据 user 消息原文生成结构化摘要，不补充外部事实，不推断未明确表达的观点",
            "input_contract": {
                "allowed_path": collection["messages_path"],
                "allowed_content": "脚本已从授权根目录的已知 JSONL schema 中筛出的 user 文本",
                "forbidden": [
                    "源 JSONL",
                    "历史根目录",
                    "source_index",
                    "其他 job artifact",
                    "assistant/system/developer/tool 内容",
                ],
                "filters_already_applied": [
                    "源与角色 schema 校验",
                    "时间窗口",
                    "已知自动注入消息",
                    "Codex 团队委派消息",
                    "重复消息",
                ],
            },
            "messages_path": collection["messages_path"],
            "summary_path": str(self.output_dir / SUMMARY_FILENAME),
            "period_keys": request["period_keys"],
            "categories": {name: title for name, title in CATEGORY_SPECS},
            "requirements": [
                "顶层只能有 periods、period_highlights、action_items、recurring_topics",
                "periods 与 period_highlights 都必须完整覆盖 period_keys 且保持相同顺序",
                "每个周期对象只能有 period、goals、constraints、decisions、acceptance、blockers",
                "period_highlights 每项为 {period, items}；items 每项用 {text, evidence}",
                "每个条目格式为 {text: 简洁忠实总结, evidence: [source-id:line]}，证据不可为空",
                "周期条目与该周期 highlights 只能引用同周期消息",
                "每个有 20 条或以上消息的周期，period_highlights 至少给出 5 个相互独立的高信息密度要点；覆盖项目、决策、验收、反馈或阻塞，不得用泛泛概括凑数",
                "action_items 只保留明确决策、待办、验收或受阻事项，格式为 {text, status, evidence}；status 只能是 pending、blocked、confirmed",
                "recurring_topics 也用 {text, evidence}，只保留至少跨两个周期的主题",
                "优先聚合一组相关发言为一个有结论、状态和后果的条目；每项尽量引用 2 至 6 条分散证据",
                "不要复制完整原文；不要加入未在 user 消息中明确支持的推测",
                "直接写合法 UTF-8 JSON，不写 Markdown 围栏",
            ],
            "empty_item_example": {"text": "用户要求保留可追溯证据", "evidence": ["source-001:12"]},
            "empty_period_example": {
                "period": request["period_keys"][0],
                "goals": [],
                "constraints": [],
                "decisions": [],
                "acceptance": [],
                "blockers": [],
            },
            "empty_highlights_example": {"period": request["period_keys"][0], "items": []},
            "action_item_example": {
                "text": "继续验证浏览器服务启动与文件回传", "status": "pending", "evidence": ["source-001:12"]
            },
        }
        json_dump(self.output_dir / BRIEF_FILENAME, brief)
        return True

    def deliver(self, artifact) -> bool:
        if SUMMARY_FILENAME not in artifact.get("files", []):
            return False
        path = Path(artifact["output_dir"]) / SUMMARY_FILENAME
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())
