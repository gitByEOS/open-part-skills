/** 地图是主界面；点节点才进入叠卡，叠卡里才能左右滑动 */

const SVG_NS = "http://www.w3.org/2000/svg";
const data = JSON.parse(document.getElementById("card-data").textContent);
const board = document.getElementById("board");
const deck = document.getElementById("deck");
const stackLayer = document.getElementById("stack-layer");
const pieceTitle = document.getElementById("piece-title");
const cardCount = document.getElementById("card-count");
const REST_POSE = [
  { x: 0, y: 0, rot: 0, scale: 1 },
  { x: -8, y: -18, rot: -6.5, scale: 0.965 },
  { x: 14, y: -34, rot: 7, scale: 0.93 },
  { x: 14, y: -22, rot: 5, scale: 0.91 },
];

function poseTransform(pose) {
  return `translateX(calc(-50% + ${pose.x}px)) translateY(${pose.y}px) rotate(${pose.rot}deg) scale(${pose.scale})`;
}

let cursor = 0;
let faceMode = "point";
let slots = [];

pieceTitle.textContent = data.title;

function indexAt(offset) {
  /** 按偏移取卡片序号，首尾相接 */
  const total = data.cards.length;
  return ((cursor + offset) % total + total) % total;
}

function splitPoint(point) {
  /** 点串与锚点交替切开 */
  const parts = [];
  let start = 0;
  while (start < point.length) {
    if (point[start] === ".") {
      let end = start + 1;
      while (end < point.length && point[end] === ".") end += 1;
      parts.push({ gap: true, text: point.slice(start, end) });
      start = end;
      continue;
    }
    let end = point.indexOf(".", start);
    if (end < 0) end = point.length;
    parts.push({ gap: false, text: point.slice(start, end) });
    start = end;
  }
  return parts;
}

function alignSegments(card) {
  /** 按锚点把原文切成空隙和关键词，两层共用这一套位置 */
  const parts = splitPoint(card.point);
  const segments = [];
  let cursor = 0;
  let index = 0;
  while (index < parts.length) {
    let dots = "";
    if (parts[index].gap) {
      dots = parts[index].text;
      index += 1;
    }
    if (index >= parts.length) {
      const rest = card.full.slice(cursor);
      if (rest) segments.push({ gap: true, full: rest, dots });
      cursor = card.full.length;
      break;
    }
    const anchor = parts[index].text;
    const found = card.full.indexOf(anchor, cursor);
    if (found < 0) return null;
    const omitted = card.full.slice(cursor, found);
    if (omitted) segments.push({ gap: true, full: omitted, dots });
    segments.push({ gap: false, text: anchor });
    cursor = found + anchor.length;
    index += 1;
  }
  if (cursor < card.full.length) {
    segments.push({ gap: true, full: card.full.slice(cursor), dots: "" });
  }
  return segments;
}

function fillAligned(node, card, mode) {
  /** 省掉的字一字一格，串联放全角点，关键词不挪位 */
  const segments = alignSegments(card);
  node.replaceChildren();
  if (!segments) {
    node.textContent = mode === "full" ? card.full : card.point;
    return;
  }
  for (const segment of segments) {
    const chars = segment.gap
      ? (mode === "full" ? segment.full : "・".repeat(segment.full.length))
      : segment.text;
    const kind = segment.gap ? "omit" : "anchor";
    for (const char of chars) {
      const cell = document.createElement("span");
      cell.className = `cell ${kind}`;
      cell.textContent = char;
      node.append(cell);
    }
  }
}

function makePin(card, index) {
  /** 地图上的一枚钉卡，只显示概述 */
  const button = document.createElement("button");
  const onLeft = index % 2 === 0;
  const tilt = (onLeft ? -1 : 1) * (1.4 + (index % 3) * 0.25);
  button.type = "button";
  button.className = `pin-card tone-${index % 3} ${onLeft ? "side-left" : "side-right"}`;
  button.style.setProperty("--rot", `${tilt}deg`);
  button.innerHTML = `<span class="pin" aria-hidden="true"></span><span class="num"></span><span class="card-title"></span><span class="body"></span>`;
  button.querySelector(".num").textContent = String(index + 1).padStart(2, "0");
  button.querySelector(".card-title").textContent = card.title;
  button.querySelector(".body").textContent = card.desc;
  button.addEventListener("click", () => openStack(index));
  return button;
}

function anchorPoint(button, boardRect, cardIndex) {
  /** 电脑朝向邻卡；手机按卡片序号交替取左 1/4、右 1/4 */
  const rect = button.getBoundingClientRect();
  const onLeft = button.classList.contains("side-left");
  const ratio = window.innerWidth <= 640
    ? (cardIndex % 2 === 0 ? 0.25 : 0.75)
    : (onLeft ? 0.75 : 0.25);
  return {
    x: rect.left + rect.width * ratio - boardRect.left,
    y: rect.top + rect.height * 0.5 - boardRect.top,
  };
}

function drawWires() {
  /** 虚线从卡片中线偏内四分之一处进出，先水平再弯向下一张 */
  const svg = board.querySelector(".wires");
  const rect = board.getBoundingClientRect();
  svg.setAttribute("width", String(rect.width));
  svg.setAttribute("height", String(rect.height));
  svg.replaceChildren();
  const buttons = [...board.querySelectorAll(".pin-card")];
  for (let index = 0; index < buttons.length - 1; index += 1) {
    const start = anchorPoint(buttons[index], rect, index);
    const end = anchorPoint(buttons[index + 1], rect, index + 1);
    const gap = end.x - start.x;
    const mobile = window.innerWidth <= 640;
    const bend = mobile
      ? Math.max(72, Math.min(160, Math.abs(gap) * 0.62))
      : Math.max(28, Math.min(88, Math.abs(gap) * 0.45));
    const dir = gap >= 0 ? 1 : -1;
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute(
      "d",
      `M ${start.x} ${start.y} C ${start.x + dir * bend} ${start.y}, ${end.x - dir * bend} ${end.y}, ${end.x} ${end.y}`,
    );
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#c5c8d0");
    path.setAttribute("stroke-width", "1.6");
    path.setAttribute("stroke-dasharray", "4 6");
    path.setAttribute("stroke-linecap", "round");
    svg.append(path);
  }
}

function paintFace(slot, offset, mode) {
  /** 叠卡只显示串联或原文 */
  const index = indexAt(offset);
  const card = data.cards[index];
  const showingPoint = mode !== "full";
  const face = slot.querySelector(".face");
  face.className = `face tone-${index % 3} mode-${showingPoint ? "point" : "full"}`;
  face.querySelector(".num").textContent = String(index + 1).padStart(2, "0");
  face.querySelector(".card-title").textContent = card.title;
  face.querySelector(".kicker").textContent = showingPoint ? "串联 · 点按看原文" : "原文 · 点按看串联";
  fillAligned(face.querySelector(".body"), card, showingPoint ? "point" : "full");
}

function makeSlot() {
  /** 造一个空槽，文案由 paintFace 填 */
  const slot = document.createElement("div");
  slot.className = "slot";
  slot.innerHTML = `<article class="face"><span class="num"></span><span class="card-title"></span><span class="kicker"></span><span class="body"></span></article>`;
  bindSlot(slot);
  return slot;
}

function place(slot, depth, isSettling = false) {
  /** 前三张可见，回收的第四张藏在最后 */
  const isHidden = depth === REST_POSE.length - 1;
  slot.style.zIndex = String(REST_POSE.length - depth);
  slot.classList.toggle("settling", isSettling);
  slot.style.transform = poseTransform(REST_POSE[depth]);
  slot.style.opacity = isHidden ? "0" : "1";
}

function showCount() {
  cardCount.textContent = `${cursor + 1} / ${data.cards.length}`;
}

function renderStack() {
  /** 从地图进入时预铺叠卡，切卡时直接轮转 */
  slots = REST_POSE.map((_, depth) => {
    const slot = makeSlot();
    paintFace(slot, depth, depth === 0 ? faceMode : "point");
    place(slot, depth);
    return slot;
  });
  deck.replaceChildren(...[...slots].reverse());
  showCount();
}

function advanceStack() {
  /** 下一张已铺好，松手即换；只重绘回收的卡槽 */
  const recycled = slots.shift();
  const depth = slots.push(recycled) - 1;
  cursor = indexAt(1);
  faceMode = "point";
  deck.prepend(recycled);
  slots.forEach((slot, index) => place(slot, index, index < depth));
  paintFace(recycled, depth, faceMode);
  recycled.querySelector(".face").scrollTop = 0;
  showCount();
}

function gestureDirection(dx, dy) {
  if (Math.hypot(dx, dy) < 8) return "pending";
  return Math.abs(dx) > Math.abs(dy) * 1.25 ? "horizontal" : "vertical";
}

function bindSlot(slot) {
  /** 纵滑交给浏览器，横滑时只移动最上面的卡 */
  let drag = null;

  function isActivePointer(event) {
    return drag?.pointerId === event.pointerId;
  }

  function cancel(event) {
    if (!isActivePointer(event)) return;
    if (drag.state === "horizontal") place(slot, 0, true);
    drag = null;
  }

  slot.addEventListener("pointerdown", (event) => {
    if (slot !== slots[0] || drag || !event.isPrimary || event.button !== 0) return;
    drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, state: "pending" };
    slot.setPointerCapture(event.pointerId);
  });

  slot.addEventListener("pointermove", (event) => {
    if (!isActivePointer(event)) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (drag.state === "pending") drag.state = gestureDirection(dx, dy);
    if (drag.state !== "horizontal") return;
    const tilt = Math.max(-8, Math.min(8, dx / 18));
    slot.classList.remove("settling");
    slot.style.transform = poseTransform({ ...REST_POSE[0], rot: tilt });
  });

  slot.addEventListener("pointerup", (event) => {
    if (!isActivePointer(event)) return;
    const dx = event.clientX - drag.x;
    const direction = gestureDirection(dx, event.clientY - drag.y);
    const { state } = drag;
    drag = null;
    if (state === "pending" && direction === "pending") {
      faceMode = faceMode === "point" ? "full" : "point";
      paintFace(slot, 0, faceMode);
    }
    if (state !== "horizontal") return;
    if (direction === "horizontal" && Math.abs(dx) > 72) {
      advanceStack();
      return;
    }
    place(slot, 0, true);
  });

  slot.addEventListener("pointercancel", cancel);
  slot.addEventListener("lostpointercapture", cancel);
}

function openStack(index) {
  /** 从被点的地图节点进入叠卡，先看串联 */
  cursor = index;
  faceMode = "point";
  stackLayer.classList.add("open");
  stackLayer.setAttribute("aria-hidden", "false");
  document.documentElement.classList.add("stack-open");
  renderStack();
}

function closeStack() {
  /** 收起叠卡，回到地图 */
  stackLayer.classList.remove("open");
  stackLayer.setAttribute("aria-hidden", "true");
  document.documentElement.classList.remove("stack-open");
  drawWires();
}

function buildMap() {
  /** 先铺地图，叠卡先藏着 */
  const wires = document.createElementNS(SVG_NS, "svg");
  wires.setAttribute("class", "wires");
  wires.setAttribute("aria-hidden", "true");
  board.append(wires);
  data.cards.forEach((card, index) => board.append(makePin(card, index)));
  drawWires();
}

document.getElementById("stack-back").addEventListener("click", closeStack);
buildMap();
window.addEventListener("resize", drawWires);
