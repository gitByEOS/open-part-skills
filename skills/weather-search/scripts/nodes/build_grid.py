"""build_grid 节点:中心 + 8 方向采样点,供 fetch_bulk 批量查询。"""

import math

from esflow import Node

EARTH_KM_PER_DEG = 111.0


class BuildGrid(Node):
    id = "build_grid"
    title = "生成采样网格"

    def run(self, ctx) -> dict:
        geo = ctx.get("geocode")
        args = ctx.get("parse_args")
        radius_km = args["radius_km"]

        lat = geo["lat"]
        lon = geo["lon"]
        dlat = radius_km / EARTH_KM_PER_DEG
        dlon = radius_km / (EARTH_KM_PER_DEG * max(math.cos(math.radians(lat)), 0.01))
        s = math.sin(math.radians(45))

        directions = [
            ("中心", 0, 0, True),
            ("北", dlat, 0, False),
            ("南", -dlat, 0, False),
            ("东", 0, dlon, False),
            ("西", 0, -dlon, False),
            ("东北", dlat * s, dlon * s, False),
            ("西北", dlat * s, -dlon * s, False),
            ("东南", -dlat * s, dlon * s, False),
            ("西南", -dlat * s, -dlon * s, False),
        ]

        points = []
        for label, d_lat, d_lon, is_center in directions:
            points.append({
                "label": label,
                "lat": round(lat + d_lat, 5),
                "lon": round(lon + d_lon, 5),
                "is_center": is_center,
            })

        return {"points": points, "radius_km": radius_km}
