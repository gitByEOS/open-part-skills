"""把 Graph / Node / Edge JSON 嵌进单文件 HTML。"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE_KINDS = {"ok", "decision", "gap", "conflict", "param"}
EDGE_KINDS = {"ok", "gap"}
LANE_IDS = {"flow", "fx", "ui"}
SEVERITIES = {"断后继", "冲突", "缺参数"}


def fail(message: str) -> None:
    raise SystemExit(message)


def load_text(name: str) -> str:
    return (ROOT / "assets" / name).read_text(encoding="utf-8")


def escape_html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def check_type(value, kind: type, where: str):
    if not isinstance(value, kind):
        names = {str: "字符串", dict: "对象", list: "数组"}
        fail(f"{where}必须是{names[kind]}")
    return value


def require(obj: dict, key: str, where: str, kind: type = str):
    if key not in obj:
        fail(f"{where} 缺少 {key}")
    return check_type(obj[key], kind, f"{where}.{key}")


def require_array(obj: dict, key: str, where: str, item_kind: type) -> list:
    values = require(obj, key, where, list)
    for index, value in enumerate(values):
        check_type(value, item_kind, f"{where}.{key}[{index}]")
    return values


def validate(data: dict) -> None:
    check_type(data, dict, "根")
    require(data, "title", "根")
    require(data, "source", "根")
    verdict = require(data, "verdict", "根", dict)
    require(verdict, "title", "verdict")
    require(verdict, "body", "verdict")
    lanes = require_array(data, "lanes", "根", dict)
    gaps = require_array(data, "gaps", "根", dict)
    if not lanes:
        fail("lanes 不能为空")
    gap_lanes = {}
    for gap in gaps:
        gap_id = require(gap, "id", "gap")
        if gap_id in gap_lanes:
            fail(f"gap 重复: {gap_id}")
        if require(gap, "severity", gap_id) not in SEVERITIES:
            fail(f"{gap_id} 的 severity 不合法")
        require(gap, "title", gap_id)
        require(gap, "fact", gap_id)
        require(gap, "need", gap_id)
        gap_lanes[gap_id] = require_array(gap, "lanes", gap_id, str)
        if not gap_lanes[gap_id]:
            fail(f"{gap_id} 的 lanes 不能为空")
    lane_ids = set()
    for lane in lanes:
        lane_id = require(lane, "id", "lane")
        if lane_id not in LANE_IDS:
            fail(f"lane id 不合法: {lane_id}")
        if lane_id in lane_ids:
            fail(f"lane 重复: {lane_id}")
        lane_ids.add(lane_id)
        require(lane, "label", lane_id)
        require(lane, "title", lane_id)
        nodes = require_array(lane, "nodes", lane_id, dict)
        edges = require_array(lane, "edges", lane_id, dict)
        if not nodes:
            fail(f"{lane_id} 没有节点")
        node_ids = set()
        for node in nodes:
            node_id = require(node, "id", lane_id)
            if node_id in node_ids:
                fail(f"{lane_id} 节点重复: {node_id}")
            node_ids.add(node_id)
            if require(node, "kind", node_id) not in NODE_KINDS:
                fail(f"{node_id} 的 kind 不合法")
            require(node, "title", node_id)
            require(node, "sub", node_id)
            require(node, "source", node_id)
            for gap_id in require_array(node, "gapIds", node_id, str):
                if gap_id not in gap_lanes:
                    fail(f"{node_id} 引用了不存在的 gap: {gap_id}")
                if lane_id not in gap_lanes[gap_id]:
                    fail(f"{lane_id} 节点 {node_id} 引用了不属于该图的 gap: {gap_id}")
        for edge in edges:
            source = require(edge, "from", lane_id)
            target = require(edge, "to", lane_id)
            if source not in node_ids or target not in node_ids:
                fail(f"{lane_id} 边端点不存在: {source} -> {target}")
            if require(edge, "kind", f"{source}->{target}") not in EDGE_KINDS:
                fail(f"{source}->{target} 的 kind 不合法")
            if "label" in edge:
                require(edge, "label", f"{source}->{target}")
        for index, row in enumerate(require_array(lane, "closed", lane_id, list)):
            if len(row) != 2:
                fail(f"{lane_id}.closed[{index}] 必须是两项")
            for cell_index, cell in enumerate(row):
                check_type(cell, str, f"{lane_id}.closed[{index}][{cell_index}]")
    for gap in gaps:
        unknown = [lane_id for lane_id in gap["lanes"] if lane_id not in lane_ids]
        if unknown:
            fail(f"{gap['id']} 指向了不存在的 lane: {', '.join(unknown)}")


def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = load_text("template.html")
    return (
        html.replace("{{TITLE}}", escape_html(data["title"]))
        .replace("{{CSS}}", load_text("viewer.css"))
        .replace("{{PELE}}", load_text("pele-flowchart.js"))
        .replace("{{JS}}", load_text("viewer.js"))
        .replace("{{DATA}}", payload)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="把衔接图 JSON 渲染成单文件 HTML")
    parser.add_argument("data", help="Graph / Node / Edge JSON")
    parser.add_argument("-o", "--output", required=True, help="输出 HTML 路径")
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    validate(data)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
