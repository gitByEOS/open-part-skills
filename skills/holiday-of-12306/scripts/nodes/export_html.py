"""export_html 节点:组装抢票条目 + 生成自包含 HTML + 打开浏览器。

扇入两个上游:holidays(节假日区间)、query_sale_time(起售时间)。
resolve_stations 车站信息经 query_sale_time 透传(read 节点产物取 station 名)。
HTML 模板内完成 ICS/CSV 下载与提醒配置,节点只负责生成与弹出。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import webbrowser
from datetime import date, timedelta
from html import escape
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log


DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "ticket-calendar"
TICKET_ADVANCE_DAYS = 15
ICS_TIMEZONE = "Asia/Shanghai"
EVENT_DURATION_MINUTES = 30
REMIND_LEAD_MINUTES = 15


def parse_sale_clock(sale_time):
    """解析起售时刻,默认 14:00。"""
    match = re.search(r"(\d{1,2}):(\d{2})", sale_time)
    if not match:
        return 14, 0
    return int(match.group(1)), int(match.group(2))


def build_ticket_entries(
    departure_station,
    departure_sale_time,
    return_station,
    return_sale_time,
    festival_periods,
    ticket_advance_days,
):
    """组装去程/返程抢票记录。festival_periods 的 start/end 为 iso 字符串。"""
    entries = []

    def append_leg(festival, period, leg, travel_day, station, sale_time):
        hour, minute = parse_sale_clock(sale_time)
        ticket_day = (date.fromisoformat(travel_day) - timedelta(days=ticket_advance_days)).isoformat()
        entries.append({
            "id": f"{leg}-{festival}",
            "festival": festival,
            "leg": leg,
            "travelDay": travel_day,
            "holidayStart": period["start"],
            "holidayEnd": period["end"],
            "ticketDay": ticket_day,
            "station": station,
            "saleHour": hour,
            "saleMinute": minute,
            "saleTime": f"{hour:02d}:{minute:02d}",
            "summary": f"{leg}抢{festival}票 · {station}",
            "description": (
                f"方向:{leg}\n"
                f"车站:{station}\n"
                f"节日:{festival}\n"
                f"假期:{period['start']} ~ {period['end']}\n"
                f"乘车日期:{travel_day}\n"
                f"预售期:{ticket_advance_days} 天\n"
                f"请以 12306 官方为准。"
            ),
        })

    for festival, period in festival_periods.items():
        append_leg(festival, period, "去程", period["start"], departure_station, departure_sale_time)
        if return_station and return_sale_time:
            append_leg(festival, period, "返程", period["end"], return_station, return_sale_time)
    return entries


def _route_title(departure_station, return_station, year):
    if return_station:
        return f"{departure_station} → {return_station} · {year} 抢票日历"
    return f"{departure_station} · {year} 抢票日历"


def _route_slug(departure_station, return_station, year):
    if return_station:
        return f"{departure_station}-{return_station}-{year}"
    return f"{departure_station}-{year}"


def _route_note(departure_station, departure_sale_time, return_station, return_sale_time):
    note = f"去程 {departure_station} 起售 {departure_sale_time}"
    if return_station and return_sale_time:
        note += f";返程 {return_station} 起售 {return_sale_time}"
    note += "。「提前 N 天」= 抢票当天 + 前 N 天。"
    return note


def generate_html_content(departure_station, return_station, year, departure_sale_time, return_sale_time, entries):
    """生成自包含 HTML:页内配置提醒并下载 ICS。"""
    payload = {
        "departureStation": departure_station,
        "returnStation": return_station,
        "hasReturnTrip": bool(return_station),
        "year": year,
        "departureSaleTime": departure_sale_time,
        "returnSaleTime": return_sale_time,
        "timezone": ICS_TIMEZONE,
        "entries": entries,
    }
    data_json = json.dumps(payload, ensure_ascii=False)
    title = _route_title(departure_station, return_station, year)
    note = _route_note(departure_station, departure_sale_time, return_station, return_sale_time)
    leg_filter_html = ""
    if return_station:
        leg_filter_html = """
        <label>
          行程
          <select id="legFilter">
            <option value="去程" selected>出发</option>
            <option value="返程">返程</option>
          </select>
        </label>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #faf8f5;
      --card: #ffffff;
      --text: #1f1f1f;
      --muted: #666;
      --accent: #c0392b;
      --border: #e8dfd4;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 2rem 1rem 3rem; }}
    .hero {{
      background: linear-gradient(135deg, #fff 0%, #fff7ef 100%);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0.85rem 1rem;
      margin-bottom: 1rem;
    }}
    h1 {{ margin: 0 0 0.35rem; font-size: 1.45rem; }}
    .hero .note {{ margin: 0 0 0.65rem; color: var(--muted); font-size: 0.92rem; }}
    .toolbar {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: center;
      margin: 0;
      font-size: 0.92rem;
    }}
    .toolbar label {{ display: inline-flex; align-items: center; gap: 0.35rem; }}
    .toolbar-actions {{
      display: flex;
      gap: 0.75rem;
      margin-left: auto;
    }}
    select, input[type="number"] {{
      padding: 0.35rem 0.5rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fff;
    }}
    input[type="number"] {{ width: 4.5rem; }}
    .btn {{
      display: inline-block;
      padding: 0.45rem 0.85rem;
      border-radius: 10px;
      text-decoration: none;
      font-weight: 600;
      border: none;
      cursor: pointer;
      font-size: 0.95rem;
    }}
    .btn-primary {{ background: var(--accent); color: #fff; }}
    .btn-secondary {{ background: #fff; color: var(--text); border: 1px solid var(--border); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}
    th, td {{ padding: 0.85rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{ background: #fff3ea; font-size: 0.92rem; }}
    tr:last-child td {{ border-bottom: none; }}
    .remind-tag {{
      display: block;
      font-size: 0.88rem;
      line-height: 1.5;
      color: var(--text);
    }}
    .note {{ margin-top: 1rem; color: var(--muted); font-size: 0.9rem; }}
    .btn-ignore {{
      padding: 0.25rem 0.55rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fff;
      color: var(--muted);
      cursor: pointer;
      font-size: 0.85rem;
    }}
    .btn-ignore:hover {{ color: var(--accent); border-color: var(--accent); }}
    .btn-restore {{
      padding: 0;
      border: none;
      background: none;
      color: var(--accent);
      cursor: pointer;
      font-size: 0.9rem;
      margin-right: 0.75rem;
    }}
    #ignoredBar {{ margin-top: 0.75rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{escape(title)}</h1>
      <p class="note" id="routeNote">{escape(note)}</p>
      <div class="toolbar">{leg_filter_html}
        <label>
          提醒方式
          <select id="remindMode">
            <option value="0" selected>当天提醒</option>
            <option value="1">提前 1 天</option>
            <option value="2">提前 2 天</option>
            <option value="3">提前 3 天</option>
          </select>
        </label>
        <label>
          提前
          <input type="number" id="remindLeadMinutes" value="{REMIND_LEAD_MINUTES}" min="1" max="120" step="1">
          分钟
        </label>
        <div class="toolbar-actions">
          <button class="btn btn-primary" id="downloadIcs" type="button">下载 ICS</button>
          <button class="btn btn-secondary" id="downloadCsv" type="button">下载 CSV</button>
        </div>
      </div>
    </section>
    <table>
      <thead>
        <tr>
          <th>节日</th>
          <th>乘车日期</th>
          <th>抢票日期</th>
          <th>车站</th>
          <th>起售时间</th>
          <th>提醒日期</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody id="calendarBody"></tbody>
    </table>
    <p class="note" id="ignoredBar" hidden></p>
    <p class="note">基于预售期 15 天生成,请以 12306 官方为准。</p>
  </div>
  <script id="calendarData" type="application/json">{data_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('calendarData').textContent);
    const remindModeEl = document.getElementById('remindMode');
    const remindLeadMinutesEl = document.getElementById('remindLeadMinutes');
    const legFilterEl = document.getElementById('legFilter');
    const routeNoteEl = document.getElementById('routeNote');
    const ignoredBarEl = document.getElementById('ignoredBar');
    const calendarBodyEl = document.getElementById('calendarBody');
    const excludedIds = new Set();

    const DEFAULT_REMIND_LEAD_MINUTES = {REMIND_LEAD_MINUTES};
    const REMIND_HELP = '「提前 N 天」= 抢票当天 + 前 N 天。';

    function getActiveLeg() {{
      if (!data.hasReturnTrip) return '去程';
      return legFilterEl.value;
    }}

    function getLegLabel(leg) {{
      return leg === '去程' ? '出发' : '返程';
    }}

    function getActiveEntries() {{
      const leg = getActiveLeg();
      return data.entries.filter((entry) => entry.leg === leg);
    }}

    function getExportEntries() {{
      return getActiveEntries().filter((entry) => !excludedIds.has(entry.id));
    }}

    function ignoreEntry(entryId) {{
      excludedIds.add(entryId);
      updateView();
    }}

    function restoreEntry(entryId) {{
      excludedIds.delete(entryId);
      updateView();
    }}

    function renderIgnoredBar() {{
      const ignored = getActiveEntries().filter((entry) => excludedIds.has(entry.id));
      if (!ignored.length) {{
        ignoredBarEl.hidden = true;
        ignoredBarEl.textContent = '';
        return;
      }}
      ignoredBarEl.hidden = false;
      ignoredBarEl.innerHTML = '已忽略:' + ignored.map((entry) => (
        '<button type="button" class="btn-restore" data-restore-id="' + entry.id + '">' +
        entry.festival + ' 恢复</button>'
      )).join('');
    }}

    function updateRouteNote() {{
      if (!data.hasReturnTrip) return;
      const leg = getActiveLeg();
      const label = getLegLabel(leg);
      const station = leg === '去程' ? data.departureStation : data.returnStation;
      const saleTime = leg === '去程' ? data.departureSaleTime : data.returnSaleTime;
      routeNoteEl.textContent = '当前' + label + ':' + station + ' 起售 ' + saleTime + '。' + REMIND_HELP;
    }}

    function pad(n) {{ return String(n).padStart(2, '0'); }}

    function getRemindLeadMinutes() {{
      const value = Number(remindLeadMinutesEl.value);
      if (!Number.isFinite(value) || value < 1) return DEFAULT_REMIND_LEAD_MINUTES;
      return Math.min(Math.round(value), 120);
    }}

    function remindClock(hour, minute, leadMinutes) {{
      let remindMinute = minute - leadMinutes;
      let remindHour = hour;
      while (remindMinute < 0) {{
        remindMinute += 60;
        remindHour -= 1;
      }}
      return {{ hour: remindHour, minute: remindMinute }};
    }}

    function formatRemindLine(day, entry) {{
      const clock = remindClock(entry.saleHour, entry.saleMinute, getRemindLeadMinutes());
      return day + ' ' + pad(clock.hour) + ':' + pad(clock.minute);
    }}

    function addDays(isoDay, offset) {{
      const parts = isoDay.split('-').map(Number);
      const date = new Date(parts[0], parts[1] - 1, parts[2] + offset);
      return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
    }}

    function getRemindDays(mode) {{
      return Number(mode);
    }}

    function reminderDates(ticketDay, remindDays) {{
      const dates = [];
      for (let offset = remindDays; offset >= 0; offset -= 1) {{
        dates.push(addDays(ticketDay, -offset));
      }}
      return dates;
    }}

    function icsDate(ticketDay, hour, minute) {{
      return ticketDay.replace(/-/g, '') + 'T' + pad(hour) + pad(minute) + '00';
    }}

    function icsEscape(text) {{
      return text
        .replace(/\\\\/g, '\\\\\\\\')
        .replace(/\\n/g, '\\\\n')
        .replace(/,/g, '\\\\,')
        .replace(/;/g, '\\\\;');
    }}

    function daysBefore(remindDay, ticketDay) {{
      const remind = remindDay.split('-').map(Number);
      const ticket = ticketDay.split('-').map(Number);
      const remindDate = new Date(remind[0], remind[1] - 1, remind[2]);
      const ticketDate = new Date(ticket[0], ticket[1] - 1, ticket[2]);
      return Math.round((ticketDate - remindDate) / 86400000);
    }}

    function eventSummary(entry, remindDay, ticketDay) {{
      const left = daysBefore(remindDay, ticketDay);
      if (left === 0) return entry.summary + '(今天开抢)';
      return entry.summary + '(还有' + left + '天)';
    }}

    function eventEnd(day, hour, minute) {{
      let endHour = hour;
      let endMinute = minute + {EVENT_DURATION_MINUTES};
      if (endMinute >= 60) {{
        endHour += 1;
        endMinute -= 60;
      }}
      return icsDate(day, endHour, endMinute);
    }}

    function buildIcs(remindDays) {{
      const leadMinutes = getRemindLeadMinutes();
      const tz = data.timezone;
      const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\\.\\d{{3}}Z$/, 'Z');
      const lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//holiday-of-12306//CN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:抢票日历-' + getLegLabel(getActiveLeg()),
        'X-WR-TIMEZONE:' + tz,
        'BEGIN:VTIMEZONE',
        'TZID:' + tz,
        'BEGIN:STANDARD',
        'DTSTART:19700101T000000',
        'TZOFFSETFROM:+0800',
        'TZOFFSETTO:+0800',
        'TZNAME:CST',
        'END:STANDARD',
        'END:VTIMEZONE',
      ];
      for (const entry of getExportEntries()) {{
        const remindList = reminderDates(entry.ticketDay, remindDays);
        const remindText = remindList.map((day) => formatRemindLine(day, entry)).join('、');
        for (const remindDay of remindList) {{
          const start = icsDate(remindDay, entry.saleHour, entry.saleMinute);
          const end = eventEnd(remindDay, entry.saleHour, entry.saleMinute);
          const summary = eventSummary(entry, remindDay, entry.ticketDay);
          const description = entry.description + '\\n抢票日期:' + entry.ticketDay + '\\n提醒日期:' + remindText;
          lines.push(
            'BEGIN:VEVENT',
            'UID:' + remindDay + '-' + entry.festival + '-' + entry.leg + '@holiday-of-12306',
            'DTSTAMP:' + stamp,
            'DTSTART;TZID=' + tz + ':' + start,
            'DTEND;TZID=' + tz + ':' + end,
            'SUMMARY:' + icsEscape(summary),
            'DESCRIPTION:' + icsEscape(description),
            'BEGIN:VALARM',
            'TRIGGER:-PT' + leadMinutes + 'M',
            'ACTION:DISPLAY',
            'DESCRIPTION:' + icsEscape(summary + ',' + leadMinutes + '分钟后起售'),
            'END:VALARM',
            'END:VEVENT'
          );
        }}
      }}
      lines.push('END:VCALENDAR');
      return lines.join('\\r\\n') + '\\r\\n';
    }}

    function buildCsv(remindDays) {{
      const rows = [['节日', '乘车日期', '抢票日期', '车站', '起售时间', '提醒日期']];
      for (const entry of getExportEntries()) {{
        const remindText = reminderDates(entry.ticketDay, remindDays)
          .map((day) => formatRemindLine(day, entry))
          .join(';');
        rows.push([
          entry.festival,
          entry.travelDay,
          entry.ticketDay,
          entry.station,
          entry.saleTime,
          remindText,
        ]);
      }}
      return rows
        .map((row) => row.map((cell) => '"' + String(cell).replace(/"/g, '""') + '"').join(','))
        .join('\\n');
    }}

    function renderTable(remindDays) {{
      const entries = getExportEntries();
      if (!entries.length) {{
        calendarBodyEl.innerHTML = (
          '<tr><td colspan="7" style="text-align:center;color:var(--muted);">当前行程已全部忽略,可在下方恢复</td></tr>'
        );
        return;
      }}
      calendarBodyEl.innerHTML = entries.map((entry) => {{
        const remindHtml = reminderDates(entry.ticketDay, remindDays)
          .map((day) => '<span class="remind-tag">' + formatRemindLine(day, entry) + '</span>')
          .join('');
        return (
          '<tr>' +
          '<td>' + entry.festival + '</td>' +
          '<td>' + entry.travelDay + '</td>' +
          '<td><strong>' + entry.ticketDay + '</strong></td>' +
          '<td>' + entry.station + '</td>' +
          '<td>' + entry.saleTime + '</td>' +
          '<td>' + remindHtml + '</td>' +
          '<td><button type="button" class="btn-ignore" data-ignore-id="' + entry.id + '">忽略</button></td>' +
          '</tr>'
        );
      }}).join('');
    }}

    function updateView() {{
      const remindDays = getRemindDays(remindModeEl.value);
      updateRouteNote();
      renderTable(remindDays);
      renderIgnoredBar();
    }}

    function downloadBlob(content, mime, filename) {{
      const blob = new Blob([content], {{ type: mime }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    }}

    function fileSlug() {{
      let slug = data.hasReturnTrip
        ? data.departureStation + '-' + data.returnStation + '-' + data.year
        : data.departureStation + '-' + data.year;
      if (data.hasReturnTrip) slug += '-' + getLegLabel(getActiveLeg());
      return slug;
    }}

    function downloadIcs() {{
      const remindDays = getRemindDays(remindModeEl.value);
      downloadBlob(
        buildIcs(remindDays),
        'text/calendar;charset=utf-8',
        'ticket-calendar-' + fileSlug() + '.ics'
      );
    }}

    function downloadCsv() {{
      const remindDays = getRemindDays(remindModeEl.value);
      downloadBlob(
        '\\ufeff' + buildCsv(remindDays),
        'text/csv;charset=utf-8',
        'ticket-calendar-' + fileSlug() + '.csv'
      );
    }}

    remindModeEl.addEventListener('change', updateView);
    remindLeadMinutesEl.addEventListener('input', updateView);
    remindLeadMinutesEl.addEventListener('change', updateView);
    if (legFilterEl) legFilterEl.addEventListener('change', updateView);
    calendarBodyEl.addEventListener('click', (event) => {{
      const ignoreBtn = event.target.closest('[data-ignore-id]');
      if (ignoreBtn) {{
        ignoreEntry(ignoreBtn.dataset.ignoreId);
        return;
      }}
    }});
    ignoredBarEl.addEventListener('click', (event) => {{
      const restoreBtn = event.target.closest('[data-restore-id]');
      if (restoreBtn) restoreEntry(restoreBtn.dataset.restoreId);
    }});
    document.getElementById('downloadIcs').addEventListener('click', downloadIcs);
    document.getElementById('downloadCsv').addEventListener('click', downloadCsv);
    updateView();
  </script>
</body>
</html>
"""


def _open_html(html_path):
    """在默认浏览器打开 HTML。"""
    if sys.platform == "darwin":
        subprocess.run(["open", str(html_path)], check=False)
    else:
        webbrowser.open(html_path.resolve().as_uri())


class ExportHtml(Node):
    id = "export_html"
    title = "生成抢票日历页"

    def accept(self, ctx) -> bool:
        """两个上游都就绪才接手;holidays/ query_sale_time 任一被跳过则跳过本节点。"""
        return ctx.get("holidays") is not None and ctx.get("query_sale_time") is not None

    def run(self, ctx) -> dict:
        holidays = ctx.get("holidays")
        sale = ctx.get("query_sale_time")
        resolved = ctx.get("resolve_stations")

        departure = resolved["departure"]["name"]
        return_station = resolved["return"]["name"] if resolved.get("return") else None
        dep_sale_time = sale["departure_sale_time"]
        ret_sale_time = sale.get("return_sale_time")
        year = holidays["year"]
        festival_periods = holidays["periods"]

        entries = build_ticket_entries(
            departure, dep_sale_time, return_station, ret_sale_time,
            festival_periods, TICKET_ADVANCE_DAYS,
        )

        out_dir = Path((self.kwargs or {}).get("out") or DEFAULT_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = _route_slug(departure, return_station, year)
        html_path = out_dir / f"ticket-calendar-{slug}.html"
        html_path.write_text(
            generate_html_content(departure, return_station, year, dep_sale_time, ret_sale_time, entries),
            encoding="utf-8",
        )

        if (self.kwargs or {}).get("open", True):
            _open_html(html_path)
        log(f"[export_html] {html_path}")
        return {
            "html_path": str(html_path),
            "departure": departure,
            "return": return_station,
            "year": year,
            "festivals": list(festival_periods.keys()),
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and Path(artifact["html_path"]).exists())
