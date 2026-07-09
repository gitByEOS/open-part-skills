"""weather-search 协议层:错误码、出门建议样式约束、stdout envelope 契约。"""

from __future__ import annotations

import json
import sys

from weather_domain import ADVICE_FILENAME

SCHEMA_VERSION = "1.0.0"
# 0 ok / 1 runtime / 2 to_agent / 3 validation
EXIT_OK, EXIT_RUNTIME, EXIT_TO_AGENT, EXIT_VALIDATION = 0, 1, 2, 3

# TO_AGENT 写 advice.md 的格式约束,stderr 与 SKILL.md 同源
ADVICE_STYLE_HINT = (
    "[样式] 出门防护建议只输出 Markdown 表格:"
    "标题为「## 外出建议」,"
    "表头固定为「日期 | 风险点 | 外出建议」,"
    "每行只写新增判断和可执行动作,不要复述上方已有数值。"
    "可合并连续同类日期,如「07-10 至 07-11」。"
    "风险点用短语,外出建议用一句话,不写表格外总结。"
    "数据优先读 analyze_grid_artifact 内 llm_text(告警段优先)或 llm_json;"
    "用 alerts、points_merged、daily_reports 判断中心与周边风险,"
    "覆盖强降水、体感高温、雷暴、低能见度、PM10 与空间极值。"
)


class CliError(Exception):
    """带稳定错误码的 CLI 异常。"""

    def __init__(self, code, message, exit_code=EXIT_RUNTIME, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable


def log(message):
    print(message, file=sys.stderr, flush=True)


def analyze_grid_artifact_path(job_dir) -> str:
    return str(job_dir / ".esflow" / "analyze_grid" / "artifact.json")


def schema():
    return {
        "ok": "boolean",
        "data": {
            "job_dir": "string path, esflow job 目录",
            "out_path": "string path, weather_report.md (end 退出)",
            "out_dir": "string path, --out 指定目录或 export 节点目录 (end 退出)",
            "analyze_grid_artifact": "string path, .esflow/analyze_grid/artifact.json (to_agent)",
            "advice_path": f"string path, agent_advice/{ADVICE_FILENAME} 写入目标 (to_agent)",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "2": "to_agent", "3": "validation"},
    }


def output_schema():
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
