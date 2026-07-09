"""parse_args 节点:从 self.kwargs 读 query + radius_km + days,校验后传出。"""

from esflow import Node

from weather_domain import DEFAULT_DAYS, DEFAULT_RADIUS_KM


class ParseArgs(Node):
    id = "parse_args"
    title = "解析入参"

    def run(self, ctx) -> dict:
        query = self.kwargs.get("query")
        radius_km = self.kwargs.get("radius_km", DEFAULT_RADIUS_KM)
        days = self.kwargs.get("days", DEFAULT_DAYS)

        if not query or not str(query).strip():
            raise ValueError("query 不能为空")

        try:
            radius_km = float(radius_km)
        except (TypeError, ValueError):
            raise ValueError(f"radius_km 必须是数字,收到 {radius_km!r}")

        if not 5 <= radius_km <= 500:
            raise ValueError(f"radius_km 必须在 5-500 之间,收到 {radius_km}")

        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValueError(f"days 必须是整数,收到 {days!r}")

        if not 1 <= days <= 16:
            raise ValueError(f"days 必须在 1-16 之间,收到 {days}")

        return {
            "query": str(query).strip(),
            "radius_km": radius_km,
            "days": days,
        }
