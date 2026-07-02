// pngya-web UI 控制层
import { optimizeFile, downloadName, MODES } from "./pngya.js";

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const modeGroup = document.getElementById("modeGroup");
const rowList = document.getElementById("rowList");
const actionsBar = document.getElementById("actionsBar");
const resultCount = document.getElementById("resultCount");
const downloadAllBtn = document.getElementById("downloadAll");
const clearAllBtn = document.getElementById("clearAll");

let currentMode = "balanced";
let exportAllModes = false;
let pendingFiles = [];
let processing = false;
/** @type {{ name: string, blob: Blob }[]} */
const downloadables = [];

// 让出主线程两帧，给浏览器渲染 pending 卡片的机会
function yieldToUI() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

modeGroup.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-mode]");
  if (!btn) return;
  modeGroup.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  if (btn.dataset.mode === "all") {
    exportAllModes = true;
  } else {
    exportAllModes = false;
    currentMode = btn.dataset.mode;
  }
});

dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) queueFiles(fileInput.files);
  fileInput.value = "";
});

let dragDepth = 0;
function isFileDrag(e) {
  return Array.from(e.dataTransfer?.types || []).includes("Files");
}

document.addEventListener("dragenter", (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault();
  dragDepth += 1;
  dropzone.classList.add("dragover");
});
document.addEventListener("dragover", (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
});
document.addEventListener("dragleave", (e) => {
  if (!isFileDrag(e)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) dropzone.classList.remove("dragover");
});
document.addEventListener("drop", (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault();
  dragDepth = 0;
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) queueFiles(e.dataTransfer.files);
});

function queueFiles(fileList) {
  pendingFiles.push(...Array.from(fileList));
  if (!processing) processQueue();
}

async function processQueue() {
  processing = true;
  actionsBar.hidden = false;
  while (pendingFiles.length) {
    const file = pendingFiles.shift();
    const modes = exportAllModes ? MODES : [currentMode];
    for (const mode of modes) {
      const placeholder = appendPendingCard(file.name, mode);
      await yieldToUI();
      const result = await optimizeFile(file, mode);
      fillCard(placeholder, result, mode);
    }
  }
  processing = false;
  refreshActions();
}

function appendPendingCard(name, mode) {
  const card = document.createElement("div");
  card.className = "file-card card-running";
  card.innerHTML = `
    <div class="file-info">
      <span class="file-name">${escapeHtml(name)}</span>
      <div class="file-meta">
        <span class="mode-tag">${mode}</span>
        <span>处理中…</span>
      </div>
    </div>
    <div class="file-actions">
      <span class="status-badge status-running">压缩中</span>
    </div>
  `;
  rowList.appendChild(card);
  refreshActions();
  return card;
}

function fillCard(card, result, mode) {
  card.classList.remove("card-running");
  const status = result.status;
  const savingPct =
    status === "optimized"
      ? Math.round((1 - result.optimizedBytes / result.originalBytes) * 100)
      : 0;

  let metaHtml = `<span class="mode-tag">${mode}</span>`;
  if (status === "optimized") {
    metaHtml += `
      <span class="size-before">${formatBytes(result.originalBytes)}</span>
      <span>→</span>
      <span class="size-after">${formatBytes(result.optimizedBytes)}</span>
      <span class="savings">-${savingPct}%</span>
      <span>${result.elapsedMs}ms</span>`;
  } else if (status === "skipped") {
    metaHtml += `<span>${formatBytes(result.originalBytes)} · 未变小 · ${result.elapsedMs}ms</span>`;
  } else {
    metaHtml += `<span class="err">${escapeHtml(result.message || "失败")}</span>`;
  }

  let actionsHtml = "";
  if (status === "optimized" && result.optimizedBlob) {
    const outName = downloadName(result.name, mode);
    downloadables.push({ name: outName, blob: result.optimizedBlob });
    actionsHtml = `<button type="button" class="btn btn-primary btn-sm dl-btn" data-name="${escapeAttr(outName)}">下载</button>`;
  } else if (status === "skipped") {
    actionsHtml = `<span class="status-badge status-skipped">已跳过</span>`;
  } else {
    actionsHtml = `<span class="status-badge status-failed">失败</span>`;
  }

  card.innerHTML = `
    <div class="file-info">
      <span class="file-name">${escapeHtml(result.name)}</span>
      <div class="file-meta">${metaHtml}</div>
    </div>
    <div class="file-actions">${actionsHtml}</div>
  `;

  const btn = card.querySelector(".dl-btn");
  if (btn) {
    btn.addEventListener("click", () => {
      const item = downloadables.find((d) => d.name === btn.dataset.name);
      if (item) triggerDownload(URL.createObjectURL(item.blob), item.name);
    });
  }
}

function refreshActions() {
  const cards = rowList.querySelectorAll(".file-card");
  const optimized = downloadables.length;
  actionsBar.hidden = cards.length === 0;
  resultCount.textContent =
    cards.length === 0 ? "" : `${optimized} 个可下载 · 共 ${cards.length} 条结果`;
  downloadAllBtn.disabled = optimized === 0 || downloadAllBtn.dataset.busy === "1";
}

downloadAllBtn.addEventListener("click", async () => {
  if (!downloadables.length) return;
  downloadAllBtn.dataset.busy = "1";
  downloadAllBtn.disabled = true;
  const label = downloadAllBtn.textContent;
  downloadAllBtn.textContent = "打包中…";
  try {
    const files = {};
    for (const { name, blob } of downloadables) {
      files[name] = new Uint8Array(await blob.arrayBuffer());
    }
    const { zipSync } = await import("https://esm.sh/fflate@0.8.2");
    const zipped = zipSync(files, { level: 6 });
    const stamp = new Date().toISOString().slice(0, 10);
    triggerDownload(
      URL.createObjectURL(new Blob([zipped], { type: "application/zip" })),
      `pngya-${stamp}.zip`,
    );
  } catch (err) {
    console.error("打包下载失败", err);
    alert(`打包失败：${err?.message || err}`);
  } finally {
    delete downloadAllBtn.dataset.busy;
    downloadAllBtn.textContent = label;
    refreshActions();
  }
});

clearAllBtn.addEventListener("click", () => {
  rowList.innerHTML = "";
  downloadables.length = 0;
  actionsBar.hidden = true;
  resultCount.textContent = "";
  downloadAllBtn.disabled = true;
});

function triggerDownload(url, name) {
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/`/g, "&#96;");
}
