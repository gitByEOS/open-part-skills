"""holiday-of-12306 flow:holidays ∥ resolve_stations → query_sale_time → export_html。

holidays 与 resolve_stations 同为入口(depth 0)并行;export_html 扇入两个上游。
无 TO_AGENT 断点,纯数据流;无返程站时 query_sale_time 返程字段为 None,
export_html 的 accept 据此跳过返程条目。
"""

from esflow import flow, edge


@flow(id="holiday-of-12306", title="12306 节假日抢票日历")
class HolidayFlow:
    nodes = ["holidays", "resolve_stations", "query_sale_time", "export_html"]
    edges = [
        edge("holidays", "export_html"),
        edge("resolve_stations", "query_sale_time"),
        edge("query_sale_time", "export_html"),
    ]
