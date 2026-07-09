"""fetch_bulk 节点:9 点坐标两次 bulk 请求(预报 + 空气质量),本地聚合成日表。"""

from openmeteo_requests import Client
import pandas as pd

from esflow import Node

from weather_domain import FORECAST_HOURLY, aggregate_hourly_frame

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


class FetchBulk(Node):
    id = "fetch_bulk"
    title = "批量拉取天气"

    def run(self, ctx) -> dict:
        grid = ctx.get("build_grid")
        args = ctx.get("parse_args")
        points = grid["points"]
        days = args["days"]

        lats = ",".join(str(p["lat"]) for p in points)
        lons = ",".join(str(p["lon"]) for p in points)
        client = Client()

        params_fc = {
            "latitude": lats,
            "longitude": lons,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "hourly": FORECAST_HOURLY,
            "forecast_days": days,
            "timezone": "auto",
        }
        params_aq = {
            "latitude": lats,
            "longitude": lons,
            "hourly": ["pm10"],
            "forecast_days": days,
            "timezone": "auto",
        }
        resp_fc = client.weather_api(FORECAST_URL, params_fc)
        resp_aq = client.weather_api(AIR_QUALITY_URL, params_aq)

        enriched = []
        for idx, point in enumerate(points):
            fc = resp_fc[idx]
            aq = resp_aq[idx]
            hourly = fc.Hourly()
            n = len(hourly.Variables(0).ValuesAsNumpy())
            local_offset = pd.to_timedelta(fc.UtcOffsetSeconds(), unit="s")
            times = pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True) + local_offset,
                periods=n,
                freq="h",
            )
            frame = pd.DataFrame({
                "time": times,
                "temp": hourly.Variables(0).ValuesAsNumpy(),
                "app_temp": hourly.Variables(1).ValuesAsNumpy(),
                "humidity": hourly.Variables(2).ValuesAsNumpy(),
                "code": hourly.Variables(3).ValuesAsNumpy(),
                "precip": hourly.Variables(4).ValuesAsNumpy(),
                "precip_prob": hourly.Variables(5).ValuesAsNumpy(),
                "snowfall": hourly.Variables(6).ValuesAsNumpy(),
                "wind": hourly.Variables(7).ValuesAsNumpy(),
                "gust": hourly.Variables(8).ValuesAsNumpy(),
                "cape": hourly.Variables(9).ValuesAsNumpy(),
                "vis": hourly.Variables(10).ValuesAsNumpy(),
            })
            aq_h = aq.Hourly()
            frame["pm10"] = aq_h.Variables(0).ValuesAsNumpy()

            daily_rows, typical_cols = aggregate_hourly_frame(frame)
            keep_dates = {row["date"] for row in daily_rows[:days]}
            typical_cols = {
                date: value
                for date, value in typical_cols.items()
                if date in keep_dates
            }
            cur = fc.Current()
            enriched.append({
                "label": point["label"],
                "lat": point["lat"],
                "lon": point["lon"],
                "is_center": point["is_center"],
                "current": {
                    "temperature": round(float(cur.Variables(0).Value()), 1),
                    "weathercode": int(cur.Variables(1).Value()),
                    "wind_speed": round(float(cur.Variables(2).Value()), 1),
                },
                "daily": daily_rows[:days],
                "typical": typical_cols,
            })

        return {"points": enriched, "days": days}
