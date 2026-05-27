#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Vigil process.md 生成固定风格的离线 HTML 报告。"""

from __future__ import annotations

import argparse
import json
import re
import webbrowser
from pathlib import Path


RISK_ORDER = ["P0", "P1", "P2", "P3", "P4", "P5"]
RISK_RANK = {risk: index for index, risk in enumerate(RISK_ORDER)}


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def read_table(lines: list[str], header: list[str]) -> list[dict[str, str]]:
    header_line = "| " + " | ".join(header) + " |"
    for index, line in enumerate(lines):
        if split_row(line) != header:
            continue
        rows: list[dict[str, str]] = []
        cursor = index + 1
        if cursor < len(lines) and is_separator(lines[cursor]):
            cursor += 1
        while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
            cells = split_row(lines[cursor])
            if cells == header or is_separator(lines[cursor]):
                cursor += 1
                continue
            if len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
            cursor += 1
        if rows:
            return rows
    raise SystemExit(f"未找到表格: {header_line}")


def strip_code(value: str) -> str:
    return re.sub(r"`([^`]+)`", r"\1", value).strip()


def split_files(value: str) -> list[str]:
    value = strip_code(value)
    return [part.strip() for part in value.split("<br>") if part.strip()]


def parse_scope(text: str) -> str:
    match = re.search(r"审查范围：(.+?)，排除 merge commit。", text)
    return match.group(1) if match else "未声明审查范围"


def risk_level(row: dict[str, str]) -> str:
    level = row.get("风险等级") or row.get("风险等级".strip()) or row.get("风险")
    if level in RISK_RANK:
        return level
    return "P5"


def sort_level(levels: list[str]) -> str:
    return sorted(levels, key=lambda item: RISK_RANK.get(item, 99))[0] if levels else "P5"


def make_pn(levels: list[str]) -> str:
    chunks = []
    for risk in RISK_ORDER:
        count = levels.count(risk)
        if count:
            chunks.append(f"{risk}={count}")
    return " ".join(chunks) or "P5=0"


def high_risk_count(levels: list[str]) -> int:
    return sum(1 for level in levels if level in {"P1", "P2"})


def from_review_rows(review_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    commits = []
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in review_rows:
        item = {
            "author": row["提交者"],
            "hash": row["CommitHash"],
            "time": row["时间"],
            "level": row["风险等级"],
            "summary": strip_code(row["存在什么风险"]),
            "files": split_files(row["哪部分代码"]),
            "test": strip_code(row["修改建议"]),
        }
        commits.append(item)
        grouped.setdefault(str(item["author"]), []).append(item)

    authors = []
    for author, rows in grouped.items():
        levels = [str(row["level"]) for row in rows]
        authors.append({
            "author": author,
            "count": len(rows),
            "pn": make_pn(levels),
            "maxRisk": sort_level(levels),
            "highRiskCount": high_risk_count(levels),
            "summary": "；".join(str(row["summary"]) for row in rows[:2]),
            "action": str(rows[0]["test"]),
        })
    authors.sort(key=lambda row: (RISK_RANK.get(str(row["maxRisk"]), 99), -int(row["highRiskCount"]), str(row["author"])))
    return authors, commits


def parse_process(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    review_header = ["提交者", "CommitHash", "时间", "修改描述", "存在什么风险", "哪部分代码", "造成风险原因", "修改建议", "风险等级"]
    author_header = ["作者", "提交数", "PN", "最高风险", "高风险 commit 数", "作者风险摘要", "优先通知动作"]
    commit_header = ["作者", "CommitHash", "时间", "风险等级", "风险摘要", "关键文件范围", "必验项"]

    review_rows = read_table(lines, review_header)
    try:
        author_rows = read_table(lines, author_header)
        commit_rows = read_table(lines, commit_header)
    except SystemExit:
        authors, commits = from_review_rows(review_rows)
    else:
        authors = [
            {
                "author": row["作者"],
                "count": int(row["提交数"]),
                "pn": row["PN"],
                "maxRisk": row["最高风险"],
                "highRiskCount": int(row["高风险 commit 数"]),
                "summary": strip_code(row["作者风险摘要"]),
                "action": strip_code(row["优先通知动作"]),
            }
            for row in author_rows
        ]
        commits = [
            {
                "author": row["作者"],
                "hash": row["CommitHash"],
                "time": row["时间"],
                "level": row["风险等级"],
                "summary": strip_code(row["风险摘要"]),
                "files": split_files(row["关键文件范围"]),
                "test": strip_code(row["必验项"]),
            }
            for row in commit_rows
        ]

    counts = {risk: 0 for risk in RISK_ORDER}
    for commit in commits:
        counts[str(commit["level"])] = counts.get(str(commit["level"]), 0) + 1

    return {
        "scope": parse_scope(text),
        "authors": authors,
        "commits": commits,
        "counts": counts,
        "total": len(commits),
        "maxRisk": sort_level([str(commit["level"]) for commit in commits]),
    }


def render_html(data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Git 提交安全审查报告</title>
  <style>
    :root { color-scheme: dark; --bg:#0b0f14; --panel:#121821; --panel-2:#18202c; --text:#e8eef7; --muted:#9aa8ba; --line:#2a3546; --p0:#d9363e; --p1:#ff4d4f; --p2:#ff9f1c; --p3:#ffd166; --p4:#73d13d; --p5:#69c0ff; }
    * { box-sizing: border-box; }
    body { margin:0; background:radial-gradient(circle at top left,#1b2636,var(--bg) 42%); color:var(--text); font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { padding:32px; border-bottom:1px solid var(--line); background:rgba(11,15,20,.78); position:sticky; top:0; z-index:10; backdrop-filter:blur(10px); }
    h1,h2,h3 { margin:0; } h1 { font-size:28px; } h2 { margin:28px 0 14px; font-size:20px; } h3 { margin:18px 0 10px; font-size:16px; color:var(--muted); }
    main { padding:24px 32px 48px; } .subtitle { color:var(--muted); margin-top:8px; }
    .alert { margin-top:18px; padding:14px 16px; border:1px solid #5c2b2b; border-left:4px solid var(--p1); background:#1c1114; border-radius:10px; font-weight:700; }
    .grid { display:grid; gap:16px; } .cards { grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); }
    .card { background:linear-gradient(180deg,var(--panel),#0f151d); border:1px solid var(--line); border-radius:14px; padding:16px; box-shadow:0 8px 24px rgba(0,0,0,.24); }
    .num { font-size:28px; font-weight:800; } .label { color:var(--muted); }
    .bar { display:grid; grid-template-columns:72px 1fr 42px; gap:10px; align-items:center; margin:8px 0; }
    .track { height:12px; background:#0c1118; border-radius:999px; overflow:hidden; border:1px solid var(--line); } .fill { height:100%; border-radius:999px; }
    .p0 { color:var(--p0); } .p1 { color:var(--p1); } .p2 { color:var(--p2); } .p3 { color:var(--p3); } .p4 { color:var(--p4); } .p5 { color:var(--p5); }
    .bg-p0 { background:var(--p0); } .bg-p1 { background:var(--p1); } .bg-p2 { background:var(--p2); } .bg-p3 { background:var(--p3); } .bg-p4 { background:var(--p4); } .bg-p5 { background:var(--p5); }
    table { width:100%; border-collapse:collapse; background:rgba(18,24,33,.94); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
    th,td { padding:12px; border-bottom:1px solid var(--line); vertical-align:top; text-align:left; }
    th { background:var(--panel-2); color:#cbd7e6; font-weight:700; }
    tr:last-child td { border-bottom:0; }
    code { color:#dbeafe; background:#0b1220; border:1px solid #24324a; padding:1px 5px; border-radius:5px; white-space:nowrap; }
    .hash { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; color:#b6c2d2; }
    .badge { display:inline-block; min-width:34px; text-align:center; padding:2px 8px; border-radius:999px; background:#0c1118; border:1px solid var(--line); font-weight:800; }
    .filters { display:flex; gap:8px; flex-wrap:wrap; margin:12px 0; }
    button { cursor:pointer; color:var(--text); background:#111827; border:1px solid var(--line); border-radius:999px; padding:8px 12px; } button.active { outline:2px solid #8ab4ff; }
    details { background:rgba(18,24,33,.72); border:1px solid var(--line); border-radius:12px; margin:12px 0; overflow:hidden; } summary { cursor:pointer; padding:12px 14px; font-weight:800; } .details-body { padding:0 14px 14px; color:var(--muted); }
    .nowrap { white-space:nowrap; }
  </style>
</head>
<body>
  <header>
    <h1>Git 提交安全审查报告</h1>
    <div class="subtitle" id="subtitle"></div>
    <div class="alert" id="alert"></div>
  </header>
  <main>
    <section>
      <h2>总体风险仪表盘</h2>
      <div class="grid cards" id="cards"></div>
      <div class="card" style="margin-top:16px" id="bars"></div>
    </section>
    <section>
      <h2>作者风险榜</h2>
      <table><thead><tr><th>作者</th><th>提交数</th><th>PN</th><th>最高风险</th><th>高风险 commit 数</th><th>作者风险摘要</th><th>优先通知动作</th></tr></thead><tbody id="authorRows"></tbody></table>
    </section>
    <section>
      <h2>按作者折叠风险列表</h2>
      <div id="authorDetails"></div>
    </section>
    <section>
      <h2>P0-P5 筛选表</h2>
      <div class="filters" id="filters"></div>
      <table><thead><tr><th>风险</th><th>作者</th><th>时间</th><th>Commit</th><th>风险摘要</th><th>关键文件范围</th><th>必验项</th></tr></thead><tbody id="commitRows"></tbody></table>
    </section>
  </main>
  <script>
    const data = __DATA__;
    const risks = ["P0","P1","P2","P3","P4","P5"];
    const cls = level => "p" + level.slice(1);
    const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[ch]));
    const badge = level => `<span class="badge ${cls(level)}">${esc(level)}</span>`;
    const codeList = files => files.map(file => `<code>${esc(file)}</code>`).join("<br>");
    const shortHash = hash => String(hash).slice(0, 10);
    const riskCount = level => data.counts[level] || 0;
    const totalCount = Math.max(1, data.total);

    document.getElementById("subtitle").textContent = `范围：${data.scope}，排除 merge commit。共 ${data.total} 个提交。`;
    document.getElementById("alert").textContent = `有 ${riskCount("P0")} 个P0隐患，请在出发前修复。当前最高风险为 ${data.maxRisk}。`;
    document.getElementById("cards").innerHTML = [
      ["提交数", data.total, ""],
      ["P1 高危", riskCount("P1"), "p1"],
      ["P2 中高风险", riskCount("P2"), "p2"],
      ["P3 中风险", riskCount("P3"), "p3"],
      ["P4 低风险", riskCount("P4"), "p4"]
    ].map(([label, value, klass]) => `<div class="card"><div class="num ${klass}">${value}</div><div class="label">${label}</div></div>`).join("");
    document.getElementById("bars").innerHTML = risks.map(risk => {
      const count = riskCount(risk);
      return `<div class="bar"><strong class="${cls(risk)}">${risk}</strong><div class="track"><div class="fill bg-${cls(risk)}" style="width:${count / totalCount * 100}%"></div></div><span>${count}</span></div>`;
    }).join("");

    document.getElementById("authorRows").innerHTML = data.authors.map(author => `
      <tr><td class="nowrap">${esc(author.author)}</td><td>${author.count}</td><td>${esc(author.pn)}</td><td>${badge(author.maxRisk)}</td><td>${author.highRiskCount}</td><td>${esc(author.summary)}</td><td>${esc(author.action)}</td></tr>
    `).join("");

    const grouped = data.commits.reduce((acc, commit) => {
      (acc[commit.author] ||= []).push(commit);
      return acc;
    }, {});
    document.getElementById("authorDetails").innerHTML = Object.entries(grouped).map(([author, rows]) => `
      <details ${rows.some(row => row.level === "P1") ? "open" : ""}>
        <summary>${esc(author)}：${rows.length} 个提交，最高 ${esc(rows.map(row => row.level).sort()[0])}</summary>
        <div class="details-body">
          ${rows.map(row => `<p>${badge(row.level)} <span class="hash">${esc(shortHash(row.hash))}</span> ${esc(row.summary)}<br>${codeList(row.files)}<br><strong>必验：</strong>${esc(row.test)}</p>`).join("")}
        </div>
      </details>
    `).join("");

    const levels = ["ALL", ...risks];
    let active = "ALL";
    function renderFilters() {
      document.getElementById("filters").innerHTML = levels.map(level => `<button class="${level === active ? "active" : ""}" onclick="setFilter('${level}')">${level}</button>`).join("");
    }
    function renderCommits() {
      const rows = data.commits.filter(commit => active === "ALL" || commit.level === active);
      document.getElementById("commitRows").innerHTML = rows.map(commit => `
        <tr>
          <td>${badge(commit.level)}</td>
          <td class="nowrap">${esc(commit.author)}</td>
          <td class="nowrap">${esc(commit.time)}</td>
          <td class="hash">${esc(shortHash(commit.hash))}</td>
          <td>${esc(commit.summary)}</td>
          <td>${codeList(commit.files)}</td>
          <td>${esc(commit.test)}</td>
        </tr>
      `).join("");
    }
    window.setFilter = level => { active = level; renderFilters(); renderCommits(); };
    renderFilters();
    renderCommits();
  </script>
</body>
</html>
""".replace("__DATA__", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="从 Vigil process.md 生成 security_report.html")
    parser.add_argument("process_md", type=Path, help="process.md 路径")
    parser.add_argument("-o", "--output", type=Path, help="输出 HTML 路径，默认写到 process.md 同目录")
    parser.add_argument("--no-open", action="store_true", help="只生成报告，不自动打开")
    args = parser.parse_args()

    process_path = args.process_md.expanduser().resolve()
    output_path = args.output.expanduser().resolve() if args.output else process_path.with_name("security_report.html")
    data = parse_process(process_path)
    output_path.write_text(render_html(data), encoding="utf-8")
    print(output_path)
    if not args.no_open:
        webbrowser.open(output_path.as_uri())


if __name__ == "__main__":
    main()
