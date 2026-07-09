"""geocode 节点:query → 中心 lat/lon,调 OpenStreetMap Nominatim。

支持城市和具体地点查询,取前 10 个候选后按名称命中和 importance 排序。
"""

import json
import urllib.parse
import urllib.request

from esflow import Node

GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "esflow-weather-skill/1.0"


def _score(hit, query):
    """候选评分:名称越贴近 query、importance 越高越靠前。"""
    display_name = hit.get("display_name", "").lower()
    name = hit.get("name", "").lower()
    normalized_query = query.lower()
    score = 0
    if name == normalized_query:
        score += 5
    if normalized_query in display_name:
        score += 2
    score += float(hit.get("importance") or 0)
    return score


class Geocode(Node):
    id = "geocode"
    title = "地点地理编码(多候选筛选)"

    def run(self, ctx) -> dict:
        args = ctx.get("parse_args")
        query_text = args["query"]

        query = urllib.parse.urlencode({
            "q": query_text,
            "format": "json",
            "addressdetails": 1,
            "limit": 10,
        })
        url = f"{GEOCODE_URL}?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
        )

        with urllib.request.urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = data or []
        if not results:
            raise ValueError(f"找不到地点: {query_text}")

        best = max(results, key=lambda h: _score(h, query_text))
        address = best.get("address") or {}
        return {
            "query": query_text,
            "display_name": best.get("display_name", query_text),
            "name": best.get("name") or best.get("display_name", query_text),
            "lat": float(best["lat"]),
            "lon": float(best["lon"]),
            "country": address.get("country", ""),
            "admin1": address.get("state") or address.get("province") or "",
            "candidates": len(results),
            "source": "nominatim",
        }
