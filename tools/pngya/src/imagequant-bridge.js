// 同源加载 libimagequant wasm，避免 CDN Worker 跨域
import init, { quantize_image } from "../vendor/imagequant/imagequant.js";

let wasmReady;

async function ensureWasm() {
  if (!wasmReady) {
    wasmReady = init(new URL("../vendor/imagequant/imagequant_bg.wasm", import.meta.url));
  }
  return wasmReady;
}

function toUint8Array(value) {
  if (value instanceof Uint8Array) return value;
  if (ArrayBuffer.isView(value)) return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  return new Uint8Array(value);
}

function paletteFromBytes(paletteBytes) {
  const palette = [];
  for (let i = 0; i < paletteBytes.length; i += 4) {
    palette.push({
      r: paletteBytes[i],
      g: paletteBytes[i + 1],
      b: paletteBytes[i + 2],
      a: paletteBytes[i + 3],
    });
  }
  return palette;
}

/** 对齐 Rust imagequant 入口：返回 palette + 每像素索引 */
export async function quantizePixels(rgba, width, height, maxColors) {
  await ensureWasm();
  const qr = quantize_image(rgba, width, height, maxColors);
  if (qr && typeof qr.free === "function" && typeof qr.palette_ptr === "function") {
    const mem = new Uint8Array((await wasmReady).memory.buffer);
    const paletteBytes = mem.slice(qr.palette_ptr(), qr.palette_ptr() + qr.palette_len());
    const indices = mem.slice(qr.indices_ptr(), qr.indices_ptr() + qr.indices_len());
    qr.free();
    return { palette: paletteFromBytes(paletteBytes), indices };
  }
  const paletteBytes = toUint8Array(qr.palette);
  const indices = toUint8Array(qr.indices);
  return { palette: paletteFromBytes(paletteBytes), indices };
}
