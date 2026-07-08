"""export_html 节点:从 aggregate.json 渲染 security_report.html。

直接消费结构化 JSON,不再从 process.md 反向解析 markdown 表格。
HTML 模板沿用 vigil_report.py 的末世暗色调风格,自包含离线可看。
"""

from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, log


HTML_TEMPLATE = """<!doctype html>
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
    document.getElementById("alert").textContent = data.alert || `当前最高风险 ${data.maxRisk}。`;
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
"""


def generate_report(aggregate_path, output_dir, *, open_browser=True):
    """从 aggregate.json 渲染 security_report.html 到 output_dir。open_browser=False 时不弹浏览器(给 CI/无头环境)。"""
    aggregate_path = Path(aggregate_path).expanduser()
    if not aggregate_path.exists():
        raise CliError("validation_error", f"缺少 aggregate.json:{aggregate_path}", EXIT_VALIDATION)
    data = json.loads(aggregate_path.read_text(encoding="utf-8"))
    # alert 文案根据实际风险等级动态生成,避免 P0=0 时仍说"请在出发前修复"
    data["alert"] = _build_alert(data)
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html_path = Path(output_dir) / "security_report.html"
    html_path.write_text(html, encoding="utf-8")
    if open_browser:
        if sys.platform == "darwin":
            subprocess.run(["open", str(html_path)], check=False)
        else:
            webbrowser.open(html_path.resolve().as_uri())
    log(f"[export_html] report -> {html_path}")
    return html_path


def _build_alert(data):
    """根据 maxRisk 与 P0 计数生成 alert 文案,避免与数据矛盾。"""
    p0 = data.get("counts", {}).get("P0", 0)
    max_risk = data.get("maxRisk", "P5")
    if p0 > 0:
        return f"有 {p0} 个 P0 隐患，请在出发前修复。当前最高风险 {max_risk}。"
    if max_risk in {"P1", "P2"}:
        return f"无 P0 隐患，但最高风险 {max_risk}，建议尽快处理。"
    if max_risk == "P3":
        return f"无 P0/P1/P2 隐患，最高风险 {max_risk}，按计划修复即可。"
    return f"无高危隐患，最高风险 {max_risk}，常规维护级别。"


class ExportHtml(Node):
    id = "export_html"
    title = "生成 HTML 报告"

    def run(self, ctx) -> dict:
        aggregate = ctx.get("aggregate") or {}
        open_browser = bool((self.kwargs or {}).get("open_browser", True))
        html_path = generate_report(aggregate["aggregate_path"], self.output_dir, open_browser=open_browser)
        return {"report_path": str(html_path)}

    def deliver(self, artifact) -> bool:
        return Path(artifact["report_path"]).exists()
