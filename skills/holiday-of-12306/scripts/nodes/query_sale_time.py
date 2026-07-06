"""query_sale_time 节点:查去程 + 返程起售时间。

依赖 resolve_stations。无返程站时返程字段返回 None,下游 export_html 据此不生成
返程条目(get_sale_time 不被调用,省一次请求)。
"""

from __future__ import annotations

import re
from datetime import date

import requests

from esflow import Node

from common import REQUEST_TIMEOUT, log


SALE_TIME_CACHE_URL = "https://kyfw.12306.cn/otn/index12306/queryAllCacheSaleTime"
SALE_TIME_PAGE_URL = "https://www.12306.cn/index/view/infos/sale_time.html"
DEFAULT_SALE_TIME = "14:00 (默认)"


def _format_sale_time(raw):
    """将 1245 或 12:45 统一为 HH:MM。"""
    raw = raw.strip()
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw[:2]}:{raw[2:]}"
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        parts = raw.split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"
    return raw


def _get_sale_time_from_cache(station_code):
    """从官方缓存接口读取起售时间。"""
    resp = requests.get(SALE_TIME_CACHE_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    for row in resp.json().get("data", []):
        if row.get("station_telecode") == station_code:
            sale_time = row.get("sale_time")
            if sale_time:
                return _format_sale_time(str(sale_time))
    return None


def _get_sale_time_from_page(station_name, station_code):
    """回退:解析 sale_time.html。"""
    today = date.today().isoformat()
    url = (
        f"{SALE_TIME_PAGE_URL}?station_name={station_name}"
        f"&station_code={station_code}&trainDate={today}"
    )
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.encoding = "utf-8"
    match = re.search(r"起售时间[：:]\s*(\d{1,2}:\d{2})", resp.text)
    if match:
        return _format_sale_time(match.group(1))
    return None


def get_sale_time(station_name, station_code):
    """查询起售时间,失败则默认 14:00 并告警。接口正常返回 14:00 时无「(默认)」后缀,可区分真假。"""
    errors = []
    for fetcher in (
        lambda: _get_sale_time_from_cache(station_code),
        lambda: _get_sale_time_from_page(station_name, station_code),
    ):
        try:
            sale_time = fetcher()
            if sale_time:
                return sale_time
        except requests.RequestException as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
    if errors:
        log(f"[query_sale_time] {station_name} 起售查询失败({'; '.join(errors)}),回落默认 14:00")
    else:
        log(f"[query_sale_time] {station_name} 起售时间未返回,回落默认 14:00")
    return DEFAULT_SALE_TIME


class QuerySaleTime(Node):
    id = "query_sale_time"
    title = "查询起售时间"

    def accept(self, ctx) -> bool:
        return ctx.get("resolve_stations") is not None

    def run(self, ctx) -> dict:
        resolved = ctx.get("resolve_stations")
        departure = resolved["departure"]
        dep_sale_time = get_sale_time(departure["name"], departure["code"])
        log(f"[query_sale_time] 去程起售:{dep_sale_time}")

        ret_sale_time = None
        return_station = resolved.get("return")
        if return_station:
            ret_sale_time = get_sale_time(return_station["name"], return_station["code"])
            log(f"[query_sale_time] 返程起售:{ret_sale_time}")

        return {"departure_sale_time": dep_sale_time, "return_sale_time": ret_sale_time}

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("departure_sale_time"))
