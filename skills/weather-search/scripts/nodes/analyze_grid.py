"""analyze_grid 节点:扇入整理九点聚合数据,极值定位,打包给表格与 agent。"""

from esflow import Node

from weather_domain import (
    format_for_llm,
    format_for_llm_json,
    merge_daily_typical,
    max_weather_risk,
    summarize_point_rows,
    weather_risk_level,
)


class AnalyzeGrid(Node):
    id = "analyze_grid"
    title = "扇入整理数据"

    def run(self, ctx) -> dict:
        grid = ctx.get("build_grid")
        bulk = ctx.get("fetch_bulk")
        args = ctx.get("parse_args")
        geo = ctx.get("geocode")
        days = args["days"]
        radius_km = grid["radius_km"]

        points_payload = []
        flat_rows = []
        for point in bulk["points"]:
            rows = merge_daily_typical(point["daily"], point["typical"])
            for row in rows:
                flat_rows.append({**row, "label": point["label"]})
            points_payload.append({
                "label": point["label"],
                "lat": point["lat"],
                "lon": point["lon"],
                "is_center": point["is_center"],
                "current": point["current"],
                "rows": rows,
                "summary": summarize_point_rows(rows),
            })

        center = next(p for p in points_payload if p["is_center"])
        around = [p for p in points_payload if not p["is_center"]]
        candidates = around or [center]
        summaries = {p["label"]: p["summary"] for p in points_payload}
        center_summary = summaries[center["label"]]

        def extreme(point, metric):
            summary = summaries[point["label"]]
            return {"point": point, "summary": summary, "value": summary[metric]}

        hottest = max(candidates, key=lambda p: summaries[p["label"]]["tmax"])
        coldest = min(candidates, key=lambda p: summaries[p["label"]]["tmin"])
        wettest = max(candidates, key=lambda p: summaries[p["label"]]["precip"])
        stormiest = max(
            candidates,
            key=lambda p: summaries[p["label"]]["weather_risk"],
        )
        gustiest = max(candidates, key=lambda p: summaries[p["label"]]["gust_max"])
        dustiest = max(candidates, key=lambda p: summaries[p["label"]]["pm10_max"])

        tmax_values = [s["tmax"] for s in summaries.values()]
        tmin_values = [s["tmin"] for s in summaries.values()]
        precip_values = [s["precip"] for s in summaries.values()]

        all_codes = [r["主要天气码"] for r in flat_rows]
        max_risk = max_weather_risk(all_codes)

        dates = sorted({r["date"] for r in center["rows"]})
        daily_reports = []
        for date in dates:
            day_by_label = {}
            for p in points_payload:
                match = next((r for r in p["rows"] if r["date"] == date), None)
                if match:
                    day_by_label[p["label"]] = {**match, "label": p["label"]}
            center_day = day_by_label.get("中心", {})
            around_days = [v for k, v in day_by_label.items() if k != "中心"]
            day_candidates = around_days or [center_day]

            daily_reports.append({
                "date": date,
                "center": center_day,
                "extremes": {
                    "hottest": max(day_candidates, key=lambda s: s["最高温"]),
                    "coldest": min(day_candidates, key=lambda s: s["最低温"]),
                    "wettest": max(day_candidates, key=lambda s: s["雨累计_mm"]),
                    "windiest": max(day_candidates, key=lambda s: s["阵风峰值"]),
                    "stormiest": max(
                        day_candidates,
                        key=lambda s: weather_risk_level(s.get("主要天气码")),
                    ),
                    "dustiest": max(day_candidates, key=lambda s: s["沙尘_pm10峰值"]),
                },
            })

        llm_text = format_for_llm(points_payload, days)
        llm_json = format_for_llm_json(flat_rows)

        return {
            "query": args["query"],
            "place": {
                "name": geo["name"],
                "display_name": geo["display_name"],
                "admin1": geo["admin1"],
                "country": geo["country"],
                "lat": geo["lat"],
                "lon": geo["lon"],
            },
            "radius_km": radius_km,
            "days": days,
            "center": center,
            "center_summary": {**center_summary, "label": center["label"]},
            "extremes": {
                "hottest": extreme(hottest, "tmax"),
                "coldest": extreme(coldest, "tmin"),
                "wettest": extreme(wettest, "precip"),
                "stormiest": extreme(stormiest, "weather_risk"),
                "gustiest": extreme(gustiest, "gust_max"),
                "dustiest": extreme(dustiest, "pm10_max"),
            },
            "spread": {
                "temperature_range": round(max(tmax_values) - min(tmin_values), 1),
                "precip_spread": round(max(precip_values) - min(precip_values), 1),
            },
            "max_risk_level": max_risk,
            "daily_reports": daily_reports,
            "points_merged": points_payload,
            "llm_text": llm_text,
            "llm_json": llm_json,
        }
