"""resolve_stations 节点:下载 12306 站名表 + 模糊匹配出发/返程站。

无上游(入口节点),与 holidays 并行。departure/return_station 由 node_args 注入。
匹配失败抛 CliError(validation_error) 列出候选,esflow 非交互不再 stdin 询问。
"""

from __future__ import annotations

import re

import requests
from difflib import SequenceMatcher

from esflow import Node

from common import CliError, EXIT_VALIDATION, REQUEST_TIMEOUT, log


STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"

# 常见末字错写 → 方位字
STATION_TYPO_MAP = {"难": "南", "兰": "南", "店": "站"}


def download_station_codes():
    """从 12306 拉取全国站名与电报码。"""
    resp = requests.get(STATION_URL, timeout=REQUEST_TIMEOUT)
    resp.encoding = "utf-8"
    match = re.search(r"var station_names\s*=\s*'([^']*)'", resp.text)
    if not match:
        raise CliError("station_error", "无法提取车站数据", EXIT_VALIDATION, True)
    stations = {}
    for item in match.group(1).split("@"):
        if not item:
            continue
        parts = item.split("|")
        if len(parts) >= 3:
            stations[parts[1]] = parts[2]
    return stations


def _station_similarity(input_name, station_name):
    """站名相似度:末字错写时给同前缀同长度站加分。"""
    ratio = SequenceMatcher(None, input_name, station_name).ratio()
    if len(input_name) == len(station_name) and len(input_name) >= 2:
        if station_name.startswith(input_name[:-1]):
            ratio += 0.15
    return ratio


def _pick_station_by_typo(input_name, candidates):
    """同分候选里,按末字常见错写优先选方位站。"""
    if len(input_name) < 2 or not candidates:
        return None
    expected = STATION_TYPO_MAP.get(input_name[-1])
    if not expected:
        return None
    for name in candidates:
        if name.endswith(expected):
            return name
    return None


def fuzzy_match_station(input_name, stations):
    """匹配站名,返回 (电报码, 站名, 候选列表)。"""
    if input_name in stations:
        return stations[input_name], input_name, []

    scored = []
    for name in stations:
        score = _station_similarity(input_name, name)
        if score >= 0.65:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], -len(item[1])))

    if not scored:
        return None, None, []

    best_score = scored[0][0]
    top = [name for score, name in scored if score >= best_score - 0.01]
    if len(top) == 1:
        matched = top[0]
        return stations[matched], matched, top

    typo_match = _pick_station_by_typo(input_name, top)
    if typo_match:
        return stations[typo_match], typo_match, top

    return None, None, top


def match_station_or_raise(input_name, stations, label):
    """匹配车站,失败抛 CliError 列出候选。"""
    code, matched_name, candidates = fuzzy_match_station(input_name.strip(), stations)
    if code is not None:
        return {"name": matched_name, "code": code}
    if candidates:
        raise CliError(
            "station_error",
            f"未精确匹配{label},候选站名:{', '.join(candidates)}",
            EXIT_VALIDATION,
        )
    raise CliError("station_error", f"无法识别{label}:{input_name}", EXIT_VALIDATION)


class ResolveStations(Node):
    id = "resolve_stations"
    title = "解析车站电报码"

    def run(self, ctx) -> dict:
        args = self.kwargs or {}
        stations = download_station_codes()
        departure = match_station_or_raise(args["departure"], stations, "出发站")
        log(f"[resolve_stations] 出发站:{departure['name']}")
        return_station = None
        if args.get("return_station"):
            return_station = match_station_or_raise(args["return_station"], stations, "返程站")
            log(f"[resolve_stations] 返程站:{return_station['name']}")
        return {"departure": departure, "return": return_station}

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("departure"))
