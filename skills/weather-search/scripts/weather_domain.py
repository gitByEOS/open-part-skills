"""天气领域常量与纯函数:拉取字段、聚合、告警与 LLM 格式化。"""

import json

DEFAULT_DAYS = 1
DEFAULT_RADIUS_KM = 5
ADVICE_FILENAME = "advice.md"

TYPICAL_HOURS = [8, 12, 16, 20]
TYPICAL_LABEL = {8: "早", 12: "中", 16: "下午", 20: "晚"}

FORECAST_HOURLY = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "weather_code",
    "precipitation",
    "precipitation_probability",
    "snowfall",
    "wind_speed_10m",
    "wind_gusts_10m",
    "cape",
    "visibility",
]

# WMO:中文/英文/严重度(0-4)
WMO_CODE_META = {
    0: ("晴", "Clear sky", 0), 1: ("大部晴", "Mainly clear", 0), 2: ("局部多云", "Partly cloudy", 0),
    3: ("阴", "Overcast", 0), 45: ("雾", "Fog", 1), 48: ("雾凇", "Rime fog", 1),
    51: ("小毛毛雨", "Light drizzle", 1), 53: ("中毛毛雨", "Moderate drizzle", 1), 55: ("大毛毛雨", "Dense drizzle", 2),
    61: ("小雨", "Slight rain", 1), 63: ("中雨", "Moderate rain", 2), 65: ("大雨", "Heavy rain", 3),
    66: ("小冻雨", "Freezing rain", 2), 67: ("大冻雨", "Heavy freezing rain", 3),
    71: ("小雪", "Slight snow", 1), 73: ("中雪", "Moderate snow", 2), 75: ("大雪", "Heavy snow", 3),
    77: ("雪粒", "Snow grains", 2),
    80: ("小阵雨", "Rain showers", 1), 81: ("中阵雨", "Moderate showers", 2), 82: ("大阵雨", "Violent showers", 3),
    85: ("小阵雪", "Snow showers", 2), 86: ("大阵雪", "Heavy snow showers", 3),
    95: ("雷暴", "Thunderstorm", 4), 96: ("雷暴+小冰雹", "Thunderstorm + hail", 4),
    99: ("雷暴+大冰雹", "Thunderstorm + heavy hail", 4),
    111: ("薄雾", "Shallow fog", 1), 113: ("霾", "Haze", 2), 114: ("沙尘", "Dust", 3),
    116: ("烟尘", "Smoke", 2), 118: ("火山灰", "Volcanic ash", 4),
}


def wmo_label(code):
    if code is None:
        return "—"
    zh, en, _risk = WMO_CODE_META.get(int(code), ("未知", "Unknown", 0))
    return f"{zh}/{en}"


def wmo_zh(code):
    if code is None:
        return "未知"
    return WMO_CODE_META.get(int(code), ("未知", "Unknown", 0))[0]


def weather_risk_level(code):
    if code is None:
        return 0
    return WMO_CODE_META.get(int(code), ("未知", "Unknown", 0))[2]


def max_weather_risk(codes):
    return max((weather_risk_level(c) for c in codes if c is not None), default=0)


def _mode_code(series):
    modes = series.mode()
    if modes.empty:
        return 0
    return int(modes.iloc[0])


def _weather_switches(series):
    return int((series.diff() != 0).sum())


def aggregate_hourly_frame(frame):
    """小时表 → 日聚合行列表 + 典型时刻列字典(按 date 字符串索引)。"""
    import pandas as pd

    df = frame.copy()
    df["hour"] = df["time"].dt.hour
    df["date"] = df["time"].dt.date
    df["gust"] = df["gust"].fillna(df["wind"])
    df = df.fillna({
        "snowfall": 0,
        "cape": 0,
        "vis": 20000,
        "precip": 0,
        "precip_prob": 0,
        "pm10": 0,
    })

    daily = df.groupby("date").agg(
        最高温=("temp", "max"),
        最低温=("temp", "min"),
        平均温=("temp", "mean"),
        温度波动=("temp", "std"),
        体感最高=("app_temp", "max"),
        体感最低=("app_temp", "min"),
        平均湿度=("humidity", "mean"),
        主要天气码=("code", _mode_code),
        天气切换=("code", _weather_switches),
        雨累计_mm=("precip", "sum"),
        雪累计_cm=("snowfall", "sum"),
        风峰值=("wind", "max"),
        阵风峰值=("gust", "max"),
        雷暴潜势_max=("cape", "max"),
        能见度_min=("vis", "min"),
        雨概峰值=("precip_prob", "max"),
        沙尘_pm10峰值=("pm10", "max"),
    ).reset_index()

    daily_rows = []
    for _, row in daily.iterrows():
        code = int(row["主要天气码"])
        daily_rows.append({
            "date": row["date"].isoformat(),
            "最高温": round(float(row["最高温"]), 1),
            "最低温": round(float(row["最低温"]), 1),
            "平均温": round(float(row["平均温"]), 1),
            "温度波动": round(float(row["温度波动"]) if pd.notna(row["温度波动"]) else 0, 2),
            "体感最高": round(float(row["体感最高"]), 1),
            "体感最低": round(float(row["体感最低"]), 1),
            "平均湿度": round(float(row["平均湿度"]), 1),
            "主要天气码": code,
            "主要天气": wmo_zh(code),
            "天气切换": int(row["天气切换"]),
            "雨累计_mm": round(float(row["雨累计_mm"]), 1),
            "雪累计_cm": round(float(row["雪累计_cm"]), 1),
            "风峰值": round(float(row["风峰值"]), 1),
            "阵风峰值": round(float(row["阵风峰值"]), 1),
            "雷暴潜势_max": round(float(row["雷暴潜势_max"]), 1),
            "能见度_min": round(float(row["能见度_min"]), 0),
            "雨概峰值": round(float(row["雨概峰值"]), 0),
            "沙尘_pm10峰值": round(float(row["沙尘_pm10峰值"]), 0),
        })

    typical_by_date = {}
    typ = df[df["hour"].isin(TYPICAL_HOURS)].copy()
    typ["时段"] = typ["hour"].map(TYPICAL_LABEL)
    for date, group in typ.groupby("date"):
        slot = {}
        for _, r in group.iterrows():
            label = r["时段"]
            slot[f"{label}温"] = round(float(r["temp"]), 1)
            slot[f"{label}体感"] = round(float(r["app_temp"]), 1)
            slot[f"{label}湿度"] = round(float(r["humidity"]), 1)
            slot[f"{label}雨"] = round(float(r["precip"]), 1)
            slot[f"{label}雪"] = round(float(r["snowfall"]), 1)
            slot[f"{label}风"] = round(float(r["wind"]), 1)
            slot[f"{label}阵风"] = round(float(r["gust"]), 1)
            slot[f"{label}pm10"] = round(float(r["pm10"]), 0)
        typical_by_date[date.isoformat()] = slot

    return daily_rows, typical_by_date


def merge_daily_typical(daily_rows, typical_by_date):
    merged = []
    for row in daily_rows:
        rec = dict(row)
        rec.update(typical_by_date.get(row["date"], {}))
        merged.append(rec)
    return merged


def day_alerts(row):
    alerts = []
    code = row.get("主要天气码") or 0
    if code >= 95:
        alerts.append(f"⚠雷暴/冰雹(码{code})")
    if code == 114:
        alerts.append("⚠沙尘")
    if row.get("体感最高", 0) >= 35:
        alerts.append(f"体感{row['体感最高']:.0f}℃")
    if row.get("雨累计_mm", 0) >= 25:
        alerts.append(f"强降水{row['雨累计_mm']:.1f}mm")
    elif row.get("雨累计_mm", 0) >= 10:
        alerts.append(f"降水{row['雨累计_mm']:.1f}mm")
    if row.get("雪累计_cm", 0) > 0:
        alerts.append(f"雪{row['雪累计_cm']:.1f}cm")
    if row.get("能见度_min", 20000) < 1000:
        alerts.append(f"能见度{row['能见度_min'] / 1000:.1f}km")
    if row.get("阵风峰值", 0) > 60:
        alerts.append(f"阵风{row['阵风峰值']:.0f}km/h")
    if row.get("沙尘_pm10峰值", 0) >= 100:
        alerts.append(f"PM10 {row['沙尘_pm10峰值']:.0f}")
    return alerts


def _slot_value(row, key):
    value = row.get(key)
    if value is None:
        return "—"
    return f"{value:.0f}"


def format_day_body(row):
    d = row["date"][5:]
    return (
        f"{d} 高{row['最高温']:.0f}/低{row['最低温']:.0f}℃ "
        f"体感{row['体感最高']:.0f}/{row['体感最低']:.0f} "
        f"{row['主要天气']} "
        f"雨{row['雨累计_mm']:.1f}mm 雪{row['雪累计_cm']:.1f}cm "
        f"风{row['风峰值']:.0f}(阵{row['阵风峰值']:.0f}) "
        f"早{_slot_value(row, '早温')}中{_slot_value(row, '中温')}"
        f"下午{_slot_value(row, '下午温')}晚{_slot_value(row, '晚温')}"
    )


def format_for_llm(points_merged, days):
    lines = [f"【未来{days}天各点位天气】"]
    for point in points_merged:
        label = point["label"]
        rows = sorted(point["rows"], key=lambda r: r["date"])
        alert_parts = []
        body_parts = []
        for row in rows:
            d = row["date"][5:]
            alerts = day_alerts(row)
            if alerts:
                alert_parts.append(f"{d}: {'|'.join(alerts)}")
            body_parts.append(format_day_body(row))
        lines.append(f"\n{label}:")
        if alert_parts:
            lines.append("  ⚠ " + " | ".join(alert_parts))
        lines.append("  " + " | ".join(body_parts))
    return "\n".join(lines)


def format_for_llm_json(rows):
    records = []
    for row in rows:
        rec = {
            "date": row["date"],
            "point": row["label"],
            "alerts": day_alerts(row),
            "summary": {
                "temp_high": row["最高温"],
                "temp_low": row["最低温"],
                "feels_like_high": row["体感最高"],
                "feels_like_low": row["体感最低"],
                "weather": row["主要天气"],
                "rain_mm": row["雨累计_mm"],
                "snow_cm": row["雪累计_cm"],
                "wind_max": row["风峰值"],
                "gust_max": row["阵风峰值"],
                "pm10_max": row["沙尘_pm10峰值"],
            },
        }
        records.append(rec)
    return json.dumps(records, ensure_ascii=False, indent=2)


def summarize_point_rows(rows):
    if not rows:
        return {}
    tmax = max(r["最高温"] for r in rows)
    tmin = min(r["最低温"] for r in rows)
    precip = round(sum(r["雨累计_mm"] for r in rows), 1)
    snow = round(sum(r["雪累计_cm"] for r in rows), 1)
    worst = max(rows, key=lambda r: (weather_risk_level(r["主要天气码"]), r["主要天气码"]))
    max_gust = max(r["阵风峰值"] for r in rows)
    max_pm10 = max(r["沙尘_pm10峰值"] for r in rows)
    return {
        "tmax": tmax,
        "tmin": tmin,
        "precip": precip,
        "snow_cm": snow,
        "weather_code": worst["主要天气码"],
        "weather_label": wmo_label(worst["主要天气码"]),
        "weather_risk": weather_risk_level(worst["主要天气码"]),
        "gust_max": max_gust,
        "pm10_max": max_pm10,
    }
