const doc = JSON.parse(document.getElementById("doc-data").textContent);
const lanes = new Map(doc.lanes.map((lane) => [lane.id, lane]));
let laneId = doc.lanes[0].id;
let selectedId = "";

const titleEl = document.getElementById("doc-title");
const sourceEl = document.getElementById("doc-source");
const verdictEl = document.getElementById("verdict");
const statsEl = document.getElementById("stats");
const lanesEl = document.getElementById("lanes");
const laneTitleEl = document.getElementById("lane-title");
const viewportEl = document.getElementById("viewport");
const asideEl = document.getElementById("aside");
const closedEl = document.getElementById("closed");
const gapsEl = document.getElementById("gaps");
const gapHeadingEl = document.getElementById("gap-heading");

titleEl.textContent = doc.title;
sourceEl.textContent = doc.source;
const verdictMark = document.createElement("span");
verdictMark.className = "mark";
verdictMark.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M8 2.2 14.2 13.2H1.8L8 2.2Z"/><path d="M8 6.4v3.2"/><path d="M8 11.5h.01" stroke-linecap="round"/></svg>';
const verdictCopy = document.createElement("div");
const verdictTitle = document.createElement("strong");
verdictTitle.textContent = doc.verdict.title;
const verdictBody = document.createElement("p");
verdictBody.textContent = doc.verdict.body;
verdictCopy.append(verdictTitle, verdictBody);
verdictEl.append(verdictMark, verdictCopy);

const view = { x: 0, y: 0, scale: 1 };
let svgEl = null;
let worldEl = null;
let graphSize = { w: 1, h: 1 };
let fittedLane = "";
let drag = null;
let blockClick = false;

function toneOf(severity) {
  if (severity === "断后继") return "danger";
  if (severity === "冲突") return "warning";
  return "info";
}

function countGaps(severity) {
  return doc.gaps.filter((gap) => gap.severity === severity).length;
}

function firstProblem(lane) {
  const node = lane.nodes.find((item) => item.kind === "gap" || item.kind === "conflict");
  return (node || lane.nodes[0]).id;
}

function renderStats() {
  statsEl.innerHTML = "";
  [
    ["断后继", countGaps("断后继"), "danger"],
    ["图文冲突", countGaps("冲突"), "warning"],
    ["缺参数", countGaps("缺参数"), "info"],
  ].forEach(([label, value, tone]) => {
    const item = document.createElement("div");
    item.className = `stat ${tone}`;
    const number = document.createElement("b");
    number.textContent = String(value);
    const name = document.createElement("span");
    name.textContent = label;
    item.append(number, name);
    statsEl.append(item);
  });
}

// 引号、Mermaid 分隔符和控制字符不能进入图语法；原文仍完整保存在侧栏和表格中。
function diagramLabel(value) {
  const clean = Array.from(value, (char) => char.charCodeAt(0) < 32 ? " " : char).join("");
  return clean.replace(/["\\[\]{}<>|;]/g, " ").replace(/\s+/g, " ").trim();
}

function mermaid(lane) {
  const ids = new Map(lane.nodes.map((node, index) => [node.id, `n${index}`]));
  const lines = ["flowchart TB"];
  lane.nodes.forEach((node) => {
    lines.push(`  ${ids.get(node.id)}["${diagramLabel(node.title)}"]`);
  });
  lane.edges.forEach((edge) => {
    const link = edge.kind === "gap" ? "-.->" : "-->";
    const label = edge.label ? `|${diagramLabel(edge.label)}|` : "";
    lines.push(`  ${ids.get(edge.from)} ${link}${label} ${ids.get(edge.to)}`);
  });
  return lines.join("\n");
}

function renderTable(table, headers, rows, tones, onRowClick) {
  table.innerHTML = "";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => {
    const cell = document.createElement("th");
    cell.textContent = header;
    if ([...String(header)].length <= 3) cell.classList.add("keep");
    headRow.append(cell);
  });
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    tr.className = tones[index] || "";
    row.forEach((value, cellIndex) => {
      const cell = document.createElement("td");
      if (cellIndex === 0) cell.className = "tone";
      if ([...String(value)].length <= 3) cell.classList.add("keep");
      cell.textContent = value;
      tr.append(cell);
    });
    if (onRowClick) {
      tr.tabIndex = 0;
      tr.addEventListener("click", () => onRowClick(index));
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onRowClick(index);
        }
      });
    }
    tbody.append(tr);
  });
  table.append(thead, tbody);
}

function renderAside(lane) {
  const node = lane.nodes.find((item) => item.id === selectedId) || lane.nodes[0];
  const gaps = node.gapIds
    .map((id) => doc.gaps.find((gap) => gap.id === id))
    .filter(Boolean);
  asideEl.innerHTML = "";
  const heading = document.createElement("h3");
  heading.textContent = node.title;
  const sub = document.createElement("p");
  sub.className = "fact";
  sub.textContent = node.sub;
  const source = document.createElement("p");
  source.textContent = node.source;
  asideEl.append(heading, sub, source);
  if (gaps.length === 0) {
    const ok = document.createElement("p");
    ok.textContent = "当前节点未关联文档缺口。";
    asideEl.append(ok);
  } else {
    gaps.forEach((gap) => {
      const name = document.createElement("p");
      const strong = document.createElement("strong");
      strong.textContent = `${gap.severity} · ${gap.title}`;
      name.append(strong);
      const fact = document.createElement("p");
      fact.className = "fact";
      fact.textContent = gap.fact;
      const need = document.createElement("p");
      need.textContent = gap.need;
      asideEl.append(name, fact, need);
    });
  }
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = "实线是已写后继，虚线是缺失或跳过。滚轮缩放，按住拖动。";
  asideEl.append(hint);
}

function applyView() {
  if (!worldEl) return;
  svgEl.setAttribute("viewBox", `0 0 ${viewportEl.clientWidth} ${viewportEl.clientHeight}`);
  worldEl.setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.scale})`);
}

function fitScale() {
  const vw = viewportEl.clientWidth || 640;
  const vh = viewportEl.clientHeight || 720;
  return Math.min((vw - 32) / graphSize.w, (vh - 32) / graphSize.h);
}

function fitView() {
  const vw = viewportEl.clientWidth || 640;
  const vh = viewportEl.clientHeight || 720;
  view.scale = fitScale();
  view.x = (vw - graphSize.w * view.scale) / 2;
  view.y = (vh - graphSize.h * view.scale) / 2;
  applyView();
}

function highlightSelection() {
  if (!svgEl) return;
  svgEl.querySelectorAll(".pele-node").forEach((el) => {
    el.classList.toggle("selected", el.dataset.nodeId === selectedId);
  });
}

function selectNode(id, reveal = false) {
  selectedId = id;
  highlightSelection();
  renderAside(lanes.get(laneId));
  if (reveal && svgEl) {
    const target = [...svgEl.querySelectorAll(".pele-node")].find((el) => el.dataset.nodeId === id);
    if (target) {
      const rect = target.getBoundingClientRect();
      const viewport = viewportEl.getBoundingClientRect();
      view.y += viewport.top + viewport.height / 2 - (rect.top + rect.height / 2);
      view.x += viewport.left + viewport.width / 2 - (rect.left + rect.width / 2);
      applyView();
    }
  }
}

function renderGraph(lane) {
  try {
    const result = ClosurePele.render(mermaid(lane), {
      idPrefix: `closure-${lane.id}-`,
      fontFamily: "system-ui, PingFang SC, sans-serif",
      fontSize: 13,
      links: false,
      images: false,
    });
    viewportEl.innerHTML = result.svg;
    svgEl = viewportEl.querySelector("svg.pele");
    if (!svgEl) throw new Error("Pele 未返回 SVG");
    svgEl.setAttribute("aria-label", lane.title);
    graphSize = { w: result.width, h: result.height };
    lane.nodes.forEach((node, index) => {
      const el = svgEl.querySelector(`.pele-node[data-id="n${index}"]`);
      if (!el) throw new Error(`Pele 缺少节点 ${node.id}`);
      el.dataset.nodeId = node.id;
      el.classList.add(`kind-${node.kind}`);
      el.setAttribute("role", "button");
      el.setAttribute("tabindex", "0");
      el.setAttribute("aria-label", `${node.title}，${node.sub}`);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${node.title} · ${node.sub}`;
      el.prepend(title);
    });
    worldEl = document.createElementNS("http://www.w3.org/2000/svg", "g");
    while (svgEl.firstChild) worldEl.append(svgEl.firstChild);
    svgEl.append(worldEl);
    svgEl.style.width = "100%";
    svgEl.style.height = "100%";
    svgEl.setAttribute("preserveAspectRatio", "none");
    if (fittedLane !== lane.id) {
      fittedLane = lane.id;
      fitView();
    } else {
      applyView();
    }
    highlightSelection();
  } catch (error) {
    svgEl = null;
    worldEl = null;
    viewportEl.textContent = `图形渲染失败：${error.message}`;
  }
}

function renderLane() {
  const lane = lanes.get(laneId);
  if (!lane.nodes.some((node) => node.id === selectedId)) selectedId = firstProblem(lane);
  laneTitleEl.textContent = lane.title;
  gapHeadingEl.textContent = `${lane.label}缺口`;
  [...lanesEl.children].forEach((button) => {
    button.classList.toggle("active", button.dataset.lane === laneId);
  });
  renderGraph(lane);
  renderAside(lane);
  renderTable(
    closedEl,
    ["衔接", "依据"],
    lane.closed,
    lane.closed.map(() => "success"),
  );
  const gaps = doc.gaps.filter((gap) => gap.lanes.includes(laneId));
  renderTable(
    gapsEl,
    ["级别", "缺口", "文档里有的", "要补上的"],
    gaps.map((gap) => [gap.severity, gap.title, gap.fact, gap.need]),
    gaps.map((gap) => toneOf(gap.severity)),
    (index) => {
      const node = lane.nodes.find((item) => item.gapIds.includes(gaps[index].id));
      if (node) selectNode(node.id, true);
    },
  );
}

doc.lanes.forEach((lane) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pill";
  button.dataset.lane = lane.id;
  button.textContent = lane.label;
  button.addEventListener("click", () => {
    laneId = lane.id;
    selectedId = firstProblem(lane);
    renderLane();
  });
  lanesEl.append(button);
});

function isDark() {
  const theme = document.documentElement.dataset.theme;
  if (theme) return theme === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function syncThemeButton() {
  document.getElementById("theme-toggle").textContent = isDark() ? "亮色" : "暗色";
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  document.documentElement.dataset.theme = isDark() ? "light" : "dark";
  syncThemeButton();
});

viewportEl.addEventListener("click", (event) => {
  if (blockClick) {
    blockClick = false;
    return;
  }
  const node = event.target.closest?.(".pele-node[data-node-id]");
  if (node) selectNode(node.dataset.nodeId);
});

viewportEl.addEventListener("keydown", (event) => {
  const node = event.target.closest?.(".pele-node[data-node-id]");
  if (node && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    selectNode(node.dataset.nodeId);
  }
});

viewportEl.addEventListener("wheel", (event) => {
  event.preventDefault();
  const rect = viewportEl.getBoundingClientRect();
  const mx = event.clientX - rect.left;
  const my = event.clientY - rect.top;
  const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
  const fit = fitScale();
  const next = Math.min(Math.max(fit, 3.5), Math.max(fit, view.scale * factor));
  const ratio = next / view.scale;
  view.x = mx - (mx - view.x) * ratio;
  view.y = my - (my - view.y) * ratio;
  view.scale = next;
  applyView();
}, { passive: false });

viewportEl.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || event.pointerType !== "mouse") return;
  blockClick = false;
  drag = { x: event.clientX, y: event.clientY, ox: view.x, oy: view.y, moved: false };
  viewportEl.classList.add("dragging");
});

window.addEventListener("pointermove", (event) => {
  if (!drag) return;
  const dx = event.clientX - drag.x;
  const dy = event.clientY - drag.y;
  if (Math.hypot(dx, dy) > 4) drag.moved = true;
  if (!drag.moved) return;
  view.x = drag.ox + dx;
  view.y = drag.oy + dy;
  applyView();
});

window.addEventListener("pointerup", () => {
  if (!drag) return;
  blockClick = drag.moved;
  drag = null;
  viewportEl.classList.remove("dragging");
});

syncThemeButton();

renderStats();
selectedId = firstProblem(doc.lanes[0]);
renderLane();
