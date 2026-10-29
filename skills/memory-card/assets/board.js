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
];

function poseTransform(pose) {
  /** 叠卡位姿，第三张和滑走进度共用同一套插值 */
  return `translateX(calc(-50% + ${pose.x}px)) translateY(${pose.y}px) rotate(${pose.rot}deg) scale(${pose.scale})`;
}

function mixPose(from, to, amount) {
  return {
    x: from.x + (to.x - from.x) * amount,
    y: from.y + (to.y - from.y) * amount,
    rot: from.rot + (to.rot - from.rot) * amount,
    scale: from.scale + (to.scale - from.scale) * amount,
  };
}

let cursor = 0;
let faceMode = "point";
let frontSlot = null;
let backSlot = null;
let farSlot = null;
let incomingSlot = null;

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
  slot.dataset.offset = String(offset);
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
  return slot;
}

function place(slot, depth, animate) {
  /** 前三张静止时都可见，第四张藏在第三张后面等着补位 */
  const hidden = depth >= 3;
  slot.style.zIndex = String(4 - depth);
  slot.style.transition = animate
    ? "transform .42s cubic-bezier(.2, .8, .2, 1), opacity .2s cubic-bezier(.45, 0, 1, 1)"
    : "none";
  slot.style.transform = poseTransform(REST_POSE[Math.min(depth, 2)]);
  slot.style.opacity = hidden ? "0" : "1";
}

function showCount() {
  cardCount.textContent = `${cursor + 1} / ${data.cards.length}`;
}

function syncBack(dx) {
  /** 拖动时透明度只动一截；补进第三张的是 1 减前方透明度 */
  if (backSlot.dataset.offset !== "1") paintFace(backSlot, 1, "point");
  if (farSlot.dataset.offset !== "2") paintFace(farSlot, 2, "point");
  if (incomingSlot.dataset.offset !== "3") paintFace(incomingSlot, 3, "point");
  const travel = Math.min(1, Math.abs(dx) / 160);
  const fade = travel * 0.18;
  frontSlot.style.opacity = String(1 - fade);
  backSlot.style.opacity = "1";
  backSlot.style.transition = "none";
  backSlot.style.transform = poseTransform(mixPose(REST_POSE[1], REST_POSE[0], travel));
  farSlot.style.opacity = "1";
  farSlot.style.transition = "none";
  farSlot.style.transform = poseTransform(mixPose(REST_POSE[2], REST_POSE[1], travel));
  incomingSlot.style.opacity = String(fade);
  incomingSlot.style.transition = "none";
  incomingSlot.style.transform = poseTransform(REST_POSE[2]);
}

function renderStack() {
  /** 重铺三张叠卡，并绑住最前面一张的拖拽 */
  deck.replaceChildren();
  incomingSlot = makeSlot();
  farSlot = makeSlot();
  backSlot = makeSlot();
  frontSlot = makeSlot();
  paintFace(incomingSlot, 3, "point");
  paintFace(farSlot, 2, "point");
  paintFace(backSlot, 1, "point");
  paintFace(frontSlot, 0, faceMode);
  place(incomingSlot, 3);
  place(farSlot, 2);
  place(backSlot, 1);
  place(frontSlot, 0);
  deck.append(incomingSlot, farSlot, backSlot, frontSlot);
  bindFront(frontSlot);
  showCount();
}

function bindFront(slot) {
  /** 轻点在串联和原文间切换，拖过阈值就斜着飞出 */
  let drag = null;

  function onMove(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const dx = event.clientX - drag.x;
    const tilt = Math.max(-22, Math.min(22, dx / 14));
    slot.style.transform = `translateX(-50%) rotate(${tilt}deg)`;
    syncBack(dx);
  }

  function onUp(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    drag = null;
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
    if (Math.hypot(dx, dy) < 8) {
      place(slot, 0, true);
      place(backSlot, 1, true);
      place(farSlot, 2, true);
      place(incomingSlot, 3, true);
      faceMode = faceMode === "point" ? "full" : "point";
      paintFace(slot, 0, faceMode);
      return;
    }
    if (Math.abs(dx) > 72) {
      fly(slot, dx > 0 ? 1 : -1);
      return;
    }
    place(slot, 0, true);
    place(backSlot, 1, true);
    place(farSlot, 2, true);
    place(incomingSlot, 3, true);
  }

  slot.addEventListener("pointerdown", (event) => {
    if (drag) return;
    drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    slot.style.transition = "none";
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  });
}

function fly(slot, dir) {
  /** dir 只决定飞出方向，落点始终是下一张 */
  const x = dir * Math.max(280, window.innerWidth * 0.72);
  slot.style.pointerEvents = "none";
  slot.style.transition = "transform .42s cubic-bezier(.2, .75, .2, 1), opacity .2s cubic-bezier(.45, 0, 1, 1)";
  slot.style.opacity = "0";
  slot.style.transform = `translateX(calc(-50% + ${x}px)) translateY(-110px) rotate(${dir * 36}deg)`;
  place(backSlot, 0, true);
  place(farSlot, 1, true);
  place(incomingSlot, 2, true);
  window.setTimeout(() => {
    cursor = indexAt(1);
    faceMode = "point";
    renderStack();
  }, 430);
}

function openStack(index) {
  /** 从被点的地图节点进入叠卡，先看串联 */
  cursor = index;
  faceMode = "point";
  stackLayer.classList.add("open");
  stackLayer.setAttribute("aria-hidden", "false");
  document.body.classList.add("stack-open");
  renderStack();
}

function closeStack() {
  /** 收起叠卡，回到地图 */
  stackLayer.classList.remove("open");
  stackLayer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("stack-open");
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
