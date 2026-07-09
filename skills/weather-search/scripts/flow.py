"""weather-search:城市 + 活动半径 N 天天气面状查询 DAG。

中心点 + 半径内 8 方向采样,bulk 两次 API 拉取,扇入聚合与 LLM 格式化,
表格汇报后交给 agent 写出门防护建议(TO_AGENT),最后落盘。
"""

from esflow import edge, flow


@flow(id="weather-search", title="天气面状查询")
class WeatherFlow:
    nodes = [
        "parse_args",
        "geocode",
        "build_grid",
        "fetch_bulk",
        "analyze_grid",
        "format_table",
        "agent_advice",
        "export",
    ]
    edges = [
        edge("parse_args", "geocode"),
        edge("geocode", "build_grid"),
        edge("build_grid", "fetch_bulk"),
        edge("fetch_bulk", "analyze_grid"),
        edge("analyze_grid", "format_table"),
        edge("format_table", "agent_advice"),
        edge("agent_advice", "export"),
    ]
