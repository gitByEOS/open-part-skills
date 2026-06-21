#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""12306 节假日抢票日历：双站匹配、起售时间、chinesecalendar → HTML/ICS。"""

import argparse
import importlib
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import date, timedelta
from difflib import SequenceMatcher

import requests

from calendar_export import export_calendar_page, open_html

STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
SALE_TIME_CACHE_URL = "https://kyfw.12306.cn/otn/index12306/queryAllCacheSaleTime"
SALE_TIME_PAGE_URL = "https://www.12306.cn/index/view/infos/sale_time.html"
TICKET_ADVANCE_DAYS = 15
REQUEST_TIMEOUT = 15

# 常见末字错写 → 方位字
STATION_TYPO_MAP = {"难": "南", "兰": "南", "店": "站"}

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


def download_station_codes():
    """从 12306 拉取全国站名与电报码。"""
    resp = requests.get(STATION_URL, timeout=REQUEST_TIMEOUT)
    resp.encoding = "utf-8"
    match = re.search(r"var station_names\s*=\s*'([^']*)'", resp.text)
    if not match:
        raise ValueError("无法提取车站数据")
    stations = {}
    for item in match.group(1).split("@"):
        if not item:
            continue
        parts = item.split("|")
        if len(parts) >= 3:
            stations[parts[1]] = parts[2]
    return stations


def _station_similarity(input_name, station_name):
    """站名相似度：末字错写时给同前缀同长度站加分。"""
    ratio = SequenceMatcher(None, input_name, station_name).ratio()
    if len(input_name) == len(station_name) and len(input_name) >= 2:
        if station_name.startswith(input_name[:-1]):
            ratio += 0.15
    return ratio


def _pick_station_by_typo(input_name, candidates):
    """同分候选里，按末字常见错写优先选方位站。"""
    if len(input_name) < 2 or not candidates:
        return None
    expected = STATION_TYPO_MAP.get(input_name[-1])
    if not expected:
        return None
    for name in candidates:
        if name.endswith(expected):
            return name
    return None


def fuzzy_match_station(input_name, stations):
    """匹配站名，返回 (电报码, 站名, 候选列表)。"""
    if input_name in stations:
        return stations[input_name], input_name, []

    scored = []
    for name in stations:
        score = _station_similarity(input_name, name)
        if score >= 0.65:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], -len(item[1])))

    if not scored:
        return None, None, []

    best_score = scored[0][0]
    top = [name for score, name in scored if score >= best_score - 0.01]
    if len(top) == 1:
        matched = top[0]
        return stations[matched], matched, top

    typo_match = _pick_station_by_typo(input_name, top)
    if typo_match:
        return stations[typo_match], typo_match, top

    return None, None, top


def _format_sale_time(raw):
    """将 1245 或 12:45 统一为 HH:MM。"""
    raw = raw.strip()
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw[:2]}:{raw[2:]}"
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        parts = raw.split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"
    return raw


def get_sale_time_from_cache(station_code):
    """从官方缓存接口读取起售时间。"""
    resp = requests.get(SALE_TIME_CACHE_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    for row in resp.json().get("data", []):
        if row.get("station_telecode") == station_code:
            sale_time = row.get("sale_time")
            if sale_time:
                return _format_sale_time(str(sale_time))
    return None


def get_sale_time_from_page(station_name, station_code):
    """回退：解析 sale_time.html。"""
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
    """查询起售时间，失败则默认 14:00。"""
    for fetcher in (
        lambda: get_sale_time_from_cache(station_code),
        lambda: get_sale_time_from_page(station_name, station_code),
    ):
        try:
            sale_time = fetcher()
            if sale_time:
                return sale_time
        except requests.RequestException:
            continue
    return "14:00 (默认)"


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
    """返回 {节日简称: {start, end}}。"""
    from chinese_calendar import get_holiday_detail, is_holiday

    min_year, max_year = get_supported_year_range()
    if year < min_year or year > max_year:
        raise ValueError(f"年份 {year} 超出 chinesecalendar 支持范围 [{min_year}, {max_year}]")

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
        ordered[label] = {"start": days[0], "end": days[-1]}
    return ordered


def get_festival_start_dates(year):
    """兼容旧接口：仅返回假期首日。"""
    return OrderedDict((label, period["start"]) for label, period in get_festival_periods(year).items())


def resolve_station(input_name, stations, label):
    """匹配车站，失败时交互确认。"""
    code, matched_name, candidates = fuzzy_match_station(input_name.strip(), stations)
    if code is None:
        if candidates:
            print(f"{label}未精确匹配，候选站名：{', '.join(candidates)}")
            if sys.stdin.isatty():
                choice = input(f"请输入{label}正确站名：").strip()
                code, matched_name, candidates = fuzzy_match_station(choice, stations)
        if code is None:
            print(f"无法识别{label}。")
            sys.exit(1)
    return code, matched_name


def get_chinese_calendar_version():
    """读取当前 chinesecalendar 版本号。"""
    import chinese_calendar

    return getattr(chinese_calendar, "__version__", "unknown")


def reload_chinese_calendar():
    """pip 升级后重新加载 chinesecalendar。"""
    import chinese_calendar
    import chinese_calendar.constants

    importlib.reload(chinese_calendar.constants)
    importlib.reload(chinese_calendar)
    return chinese_calendar


def ensure_holidays_updated(quiet=False):
    """升级 chinesecalendar；quiet 时仅输出一行摘要。"""
    if not quiet:
        print("正在更新 chinesecalendar 库...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "chinesecalendar"],
        check=False,
        capture_output=quiet,
        text=quiet,
    )
    if result.returncode != 0:
        print("更新失败，请检查 pip 和网络连接。", file=sys.stderr)
        sys.exit(1)

    importlib.invalidate_caches()
    try:
        reload_chinese_calendar()
    except ImportError:
        print("更新失败，无法导入 chinese_calendar。", file=sys.stderr)
        sys.exit(1)

    version = get_chinese_calendar_version()
    if quiet:
        print(f"节假日库已同步（v{version}）")
        return

    print(f"更新成功！当前 chinesecalendar 版本：{version}")
    min_year, max_year = get_supported_year_range()
    test_year = min(date.today().year + 1, max_year)
    print(f"\n测试 {test_year} 年节假日获取（库支持 [{min_year}, {max_year}]）：")
    try:
        get_festival_periods(test_year)
    except ValueError as err:
        print(f"  {err}", file=sys.stderr)
        sys.exit(1)
    periods = get_festival_periods(test_year)
    if not periods:
        print("  未获取到数据，库可能尚未包含该年安排。", file=sys.stderr)
        sys.exit(1)
    for fest, period in get_festival_periods(test_year).items():
        print(f"  {fest}: {period['start']} ~ {period['end']}")
    print("\n节假日数据库已更新至最新版本。")


def run_calendar(departure_name, return_name, year, skip_update=False):
    if not skip_update:
        ensure_holidays_updated(quiet=True)

    min_year, max_year = get_supported_year_range()
    if year < min_year or year > max_year:
        print(
            f"年份 {year} 超出 chinesecalendar 支持范围 [{min_year}, {max_year}]，"
            "请稍后重试或等待 chinesecalendar 发布新版本。"
        )
        sys.exit(1)

    print("正在获取车站代码...")
    stations = download_station_codes()
    dep_code, dep_station = resolve_station(departure_name, stations, "出发站")
    print(f"出发站：{dep_station}")

    ret_station = None
    ret_code = None
    ret_sale_time = None
    if return_name:
        ret_code, ret_station = resolve_station(return_name, stations, "返程站")
        print(f"返程站：{ret_station}")

    print("正在查询起售时间...")
    dep_sale_time = get_sale_time(dep_station, dep_code)
    print(f"去程起售：{dep_sale_time}")
    if ret_station:
        ret_sale_time = get_sale_time(ret_station, ret_code)
        print(f"返程起售：{ret_sale_time}")

    print(f"正在获取 {year} 年节假日安排（chinesecalendar）...")
    festival_periods = get_festival_periods(year)
    if not festival_periods:
        print("获取失败，请检查 chinesecalendar 是否已更新。")
        sys.exit(1)

    html_path = export_calendar_page(
        dep_station,
        ret_station,
        year,
        dep_sale_time,
        ret_sale_time,
        festival_periods,
        TICKET_ADVANCE_DAYS,
    )
    open_html(html_path)
    print(f"已打开抢票日历：{html_path}")
    print("在网页中选择提醒方式后，点击「下载 ICS」导入系统日历。")


def parse_route_args(departure, arg2, arg3):
    """解析 出发站 [返程站] [年份]。"""
    if arg2 is None:
        return departure, None, date.today().year
    if re.fullmatch(r"\d{4}", arg2):
        return departure, None, int(arg2)
    year = arg3 if arg3 is not None else date.today().year
    return departure, arg2, year


def build_parser():
    parser = argparse.ArgumentParser(description="12306 节假日抢票日历（出发站 + 可选返程站）")
    parser.add_argument("--update", action="store_true", help="仅升级 chinesecalendar 并自检，不生成日历")
    parser.add_argument("--skip-update", action="store_true", help="跳过默认的节假日库同步")
    parser.add_argument("departure", nargs="?", help="出发站名，如 北京南")
    parser.add_argument("return_station", nargs="?", help="返程站名，如 天津西；省略则仅生成去程")
    parser.add_argument("year", nargs="?", type=int, help="目标年份，默认当前年")
    return parser


def main():
    args = build_parser().parse_args()
    if args.update:
        ensure_holidays_updated(quiet=False)
        return
    if not args.departure:
        build_parser().print_help()
        sys.exit(1)
    departure, return_station, year = parse_route_args(
        args.departure,
        args.return_station,
        args.year,
    )
    run_calendar(departure, return_station, year, skip_update=args.skip_update)


if __name__ == "__main__":
    main()
