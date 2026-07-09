"""format_table 节点:生成面向用户的 Markdown 摘要。"""

from esflow import Node

from weather_domain import day_alerts, wmo_label, wmo_zh


class FormatTable(Node):
    id = "format_table"
    title = "生成数据汇报"

    def run(self, ctx) -> dict:
        agg = ctx.get("analyze_grid")
        center = agg["center"]
        cur = center["current"]
        center_summary = agg["center_summary"]
        extremes = agg["extremes"]
        place = agg["place"]
        daily_reports = agg["daily_reports"]
        llm_text = agg["llm_text"]
        center_alerts = []
        for row in center["rows"]:
            center_alerts.extend(f"{row['date']} {alert}" for alert in day_alerts(row))
        spatial_alerts = []
        for report in daily_reports:
            stormiest = report["extremes"]["stormiest"]
            for alert in day_alerts(stormiest):
                if stormiest["label"] != center["label"] or alert.startswith("⚠"):
                    spatial_alerts.append(f"{report['date']} {stormiest['label']} {alert}")
        all_alerts = list(dict.fromkeys(spatial_alerts + center_alerts))

        lines = []
        lines.append(f"# {place['name']} 天气面状查询报告\n")
        lines.append(f"> 查询: {agg['query']} · 命中: {place['display_name']}")
        lines.append(
            f"> 活动半径: {agg['radius_km']:.0f} km · 预报天数: {agg['days']} · 采样点: 9(中心+8方向)\n"
        )

        lines.append("## 中心点当前天气\n")
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| 温度 | {cur.get('temperature'):.1f} °C |")
        lines.append(f"| 天气 | {wmo_zh(cur.get('weathercode'))} |")
        lines.append(f"| 风速 | {cur.get('wind_speed'):.1f} km/h |\n")

        lines.append("## 风险概览\n")
        if all_alerts:
            for alert in all_alerts[:8]:
                lines.append(f"- {alert}")
        else:
            lines.append("- 中心点暂无强天气告警")
        lines.append("")

        lines.append("## 中心点逐日预报\n")
        lines.append("| 日期 | 天气 | 高/低(°C) | 雨(mm) | 雪(cm) | 阵风(km/h) | PM10 | 告警 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for row in center["rows"]:
            alerts = " · ".join(day_alerts(row)) or "—"
            lines.append(
                f"| {row['date']} | {row['主要天气']} | {row['最高温']}/{row['最低温']} | "
                f"{row['雨累计_mm']} | {row['雪累计_cm']} | {row['阵风峰值']} | "
                f"{row['沙尘_pm10峰值']:.0f} | {alerts} |"
            )

        lines.append("\n## 半径内极值对比\n")
        lines.append("| 极值类型 | 出现方向 | 中心值 | 周边极值 |")
        lines.append("|---|---|---|---|")
        lines.append(
            f"| 最高温 | {extremes['hottest']['point']['label']} | {center_summary['tmax']} | "
            f"{extremes['hottest']['value']} |"
        )
        lines.append(
            f"| 最低温 | {extremes['coldest']['point']['label']} | {center_summary['tmin']} | "
            f"{extremes['coldest']['value']} |"
        )
        lines.append(
            f"| 累计降水 | {extremes['wettest']['point']['label']} | {center_summary['precip']:.1f} | "
            f"{extremes['wettest']['value']:.1f} |"
        )
        lines.append(
            f"| 最恶劣天气 | {extremes['stormiest']['point']['label']} | {wmo_zh(center_summary['weather_code'])} | "
            f"{wmo_zh(extremes['stormiest']['summary']['weather_code'])} |"
        )
        lines.append(
            f"| 最大阵风 | {extremes['gustiest']['point']['label']} | {center_summary['gust_max']:.0f} | "
            f"{extremes['gustiest']['value']:.0f} |"
        )
        lines.append(
            f"| PM10 峰值 | {extremes['dustiest']['point']['label']} | {center_summary['pm10_max']:.0f} | "
            f"{extremes['dustiest']['value']:.0f} |"
        )
        spread = agg["spread"]
        lines.append(
            f"\n> 半径内温差跨度: {spread['temperature_range']} °C · 降水差: {spread['precip_spread']} mm\n"
        )

        lines.append("## 逐日空间风险\n")
        for report in daily_reports:
            date = report["date"]
            ex = report["extremes"]
            lines.append(
                f"**{date}** 高温 {ex['hottest']['label']} {ex['hottest']['最高温']}°C · "
                f"降水 {ex['wettest']['label']} {ex['wettest']['雨累计_mm']}mm · "
                f"阵风 {ex['windiest']['label']} {ex['windiest']['阵风峰值']}km/h · "
                f"PM10 {ex['dustiest']['label']} {ex['dustiest']['沙尘_pm10峰值']:.0f} · "
                f"最高风险 {ex['stormiest']['label']} {ex['stormiest']['主要天气']}"
            )
        lines.append("")

        lines.append("---")

        markdown = "\n".join(lines) + "\n"
        return {
            "markdown": markdown,
            "llm_text": llm_text,
            "chars": len(markdown),
            "query": agg["query"],
            "place_name": place["name"],
        }
