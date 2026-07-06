"""holidays 节点:升级 chinesecalendar + 取目标年份节假日区间。

无上游(入口节点),与 resolve_stations 并行。year/skip_update/verbose 由 node_args 注入。
verbose=True 时(--update 模式)打印升级过程与测试年节假日自检;正常 flow 静默。
date 转 iso 字符串便于 artifact JSON 持久化,下游 export_html 直接读字符串。
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from collections import OrderedDict
from datetime import date, timedelta

from esflow import Node

from common import CliError, EXIT_RUNTIME, EXIT_VALIDATION, log


# chinesecalendar 返回英文节日名 → 输出简称
FESTIVAL_KEYS = OrderedDict([
    ("元旦", "New Year's Day"),
    ("春节", "Spring Festival"),
    ("清明", "Tomb-sweeping Day"),
    ("劳动节", "Labour Day"),
    ("端午", "Dragon Boat Festival"),
    ("中秋", "Mid-autumn Festival"),
    ("国庆", "National Day"),
])


def iter_year_dates(year):
    """遍历指定年份的全部日期。"""
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def get_supported_year_range():
    """读取 chinesecalendar 支持的年份区间。"""
    import chinese_calendar.constants as constants

    years = [day.year for day in constants.holidays.keys()]
    return min(years), max(years)


def get_festival_periods(year):
    """返回 OrderedDict {节日简称: {"start": iso, "end": iso}}。date 转字符串便于 JSON 持久化。"""
    from chinese_calendar import get_holiday_detail, is_holiday

    min_year, max_year = get_supported_year_range()
    if year < min_year or year > max_year:
        raise CliError(
            "holiday_error",
            f"年份 {year} 超出 chinesecalendar 支持范围 [{min_year}, {max_year}]",
            EXIT_VALIDATION,
        )

    english_to_label = {english: label for label, english in FESTIVAL_KEYS.items()}
    festival_days = {}

    for day in iter_year_dates(year):
        if not is_holiday(day):
            continue
        on_holiday, holiday_name = get_holiday_detail(day)
        if not on_holiday or not holiday_name:
            continue
        label = english_to_label.get(holiday_name)
        if label:
            festival_days.setdefault(label, []).append(day)

    ordered = OrderedDict()
    for label in FESTIVAL_KEYS:
        days = festival_days.get(label)
        if not days:
            continue
        days.sort()
        ordered[label] = {"start": days[0].isoformat(), "end": days[-1].isoformat()}
    if not ordered:
        raise CliError("holiday_error", f"{year} 年未获取到节假日数据,请检查 chinesecalendar 是否已更新", EXIT_RUNTIME)
    return ordered


def _reload_chinese_calendar():
    """pip 升级后重新加载 chinesecalendar。"""
    import chinese_calendar
    import chinese_calendar.constants

    importlib.reload(chinese_calendar.constants)
    importlib.reload(chinese_calendar)
    return chinese_calendar


def upgrade_chinese_calendar(quiet=True):
    """升级 chinesecalendar 并 reload,返回新版本号。quiet 时仅错误输出。"""
    if not quiet:
        print("正在更新 chinesecalendar 库...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "chinesecalendar"],
        check=False,
        capture_output=quiet,
        text=quiet,
    )
    if result.returncode != 0:
        raise CliError("holiday_error", "更新 chinesecalendar 失败,请检查 pip 和网络连接", EXIT_RUNTIME, True)

    importlib.invalidate_caches()
    try:
        chinese_calendar = _reload_chinese_calendar()
    except ImportError as exc:
        raise CliError("holiday_error", "更新失败,无法导入 chinese_calendar", EXIT_RUNTIME) from exc
    return getattr(chinese_calendar, "__version__", "unknown")


def _self_check(version):
    """verbose 模式自检:打印库支持区间与测试年节假日。"""
    min_year, max_year = get_supported_year_range()
    test_year = min(date.today().year + 1, max_year)
    print(f"更新成功!当前 chinesecalendar 版本:{version}")
    print(f"库支持 [{min_year}, {max_year}],测试 {test_year} 年节假日:")
    for fest, period in get_festival_periods(test_year).items():
        print(f"  {fest}: {period['start']} ~ {period['end']}")
    print("节假日数据库已更新至最新版本。")


class Holidays(Node):
    id = "holidays"
    title = "获取节假日区间"

    def run(self, ctx) -> dict:
        args = self.kwargs or {}
        year = args["year"]
        verbose = args.get("verbose", False)

        if not args.get("skip_update"):
            version = upgrade_chinese_calendar(quiet=not verbose)
            if verbose:
                _self_check(version)
            else:
                log(f"节假日库已同步(v{version})")

        periods = get_festival_periods(year)
        log(f"[holidays] {year} 年 {len(periods)} 个节假日")
        return {"year": year, "periods": dict(periods)}

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("periods"))
