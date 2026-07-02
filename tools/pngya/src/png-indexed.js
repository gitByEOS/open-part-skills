// indexed PNG 编码，对齐 crates/pngya-core encode_indexed_png
import { zlibSync } from "https://esm.sh/fflate@0.8.2";

function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) {
    crc ^= bytes[i];
    for (let k = 0; k < 8; k += 1) {
      const mask = -(crc & 1);
      crc = (crc >>> 1) ^ (0xedb88320 & mask);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const tag = new TextEncoder().encode(type);
  const out = new Uint8Array(12 + data.length);
  const view = new DataView(out.buffer);
  view.setUint32(0, data.length);
  out.set(tag, 4);
  out.set(data, 8);
  view.setUint32(8 + data.length, crc32(out.subarray(4, 8 + data.length)));
  return out;
}

export function encodeIndexedPng(width, height, palette, indexedPixels) {
  const plte = new Uint8Array(palette.length * 3);
  const trns = [];
  for (let i = 0; i < palette.length; i += 1) {
    const c = palette[i];
    plte[i * 3] = c.r;
    plte[i * 3 + 1] = c.g;
    plte[i * 3 + 2] = c.b;
    trns.push(c.a);
  }
  while (trns.length > 0 && trns[trns.length - 1] === 255) trns.pop();

  const rowBytes = 1 + width;
  const raw = new Uint8Array(height * rowBytes);
  for (let y = 0; y < height; y += 1) {
    const rowStart = y * rowBytes;
    raw[rowStart] = 0;
    raw.set(indexedPixels.subarray(y * width, (y + 1) * width), rowStart + 1);
  }
  const idat = zlibSync(raw);

  const ihdr = new Uint8Array(13);
  const iv = new DataView(ihdr.buffer);
  iv.setUint32(0, width);
  iv.setUint32(4, height);
  ihdr[8] = 8;
  ihdr[9] = 3;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const parts = [
    new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk("IHDR", ihdr),
    pngChunk("PLTE", plte),
  ];
  if (trns.length > 0) parts.push(pngChunk("tRNS", new Uint8Array(trns)));
  parts.push(pngChunk("IDAT", idat), pngChunk("IEND", new Uint8Array()));

  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    out.set(p, off);
    off += p.length;
  }
  return out;
}
