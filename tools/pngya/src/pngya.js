// pngya-web：对齐 crates/pngya-core 四档 PNG/JPG 策略
import { optimise as oxipngOptimize } from "https://esm.sh/@jsquash/oxipng@2.3.0";
import { decode as pngDecode } from "https://esm.sh/@jsquash/png@3.1.1";
import { encode as jpegEncode, decode as jpegDecode } from "https://esm.sh/@jsquash/jpeg@1.6.0";
import { encodeIndexedPng } from "./png-indexed.js";
import { quantizePixels } from "./imagequant-bridge.js";

export const MODES = ["quality", "balanced", "compact", "extreme"];

const LOSSY_MIN_BYTES = 64 * 1024;

const JPEG_QUALITY = {
  quality: 100,
  balanced: 88,
  compact: 82,
  extreme: 60,
};

const OXIPNG_LEVEL = {
  quality: 1,
  balanced: 3,
  compact: 6,
  extreme: 6,
};

const QUANTIZED_OXIPNG_LEVEL = {
  quality: 3,
  balanced: 3,
  compact: 6,
  extreme: 6,
};

function detectFormat(file) {
  const name = file.name.toLowerCase();
  if (name.endsWith(".png")) return "png";
  if (name.endsWith(".jpg") || name.endsWith(".jpeg")) return "jpg";
  return null;
}

function oxipng(bytes, level) {
  return oxipngOptimize(bytes, { level, optimizeAlpha: true });
}

function smallerOutput(a, b) {
  return b.byteLength < a.byteLength ? b : a;
}

function clearTransparentRgb(data) {
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] === 0) {
      data[i] = 0;
      data[i + 1] = 0;
      data[i + 2] = 0;
    }
  }
}

function uniqueNormalizedColors(data) {
  const set = new Set();
  for (let i = 0; i < data.length; i += 4) {
    set.add(`${data[i]},${data[i + 1]},${data[i + 2]},${data[i + 3]}`);
  }
  return set.size;
}

function quantizeStrategyForUniqueColors(uniqueColors) {
  if (uniqueColors <= 128) {
    return { maxColors: Math.max(uniqueColors, 2), dithering: 0 };
  }
  if (uniqueColors <= 4096) {
    return { maxColors: 128, dithering: 0 };
  }
  return { maxColors: 256, dithering: 0.75 };
}

async function optimizePngLossy(bytes, mode) {
  const decoded = await pngDecode(bytes);
  const { width, height } = decoded;
  const rgba = new Uint8Array(decoded.data);
  clearTransparentRgb(rgba);
  const strategy = quantizeStrategyForUniqueColors(uniqueNormalizedColors(rgba));

  const { palette, indices } = await quantizePixels(
    rgba,
    width,
    height,
    strategy.maxColors,
  );

  const indexedPng = encodeIndexedPng(width, height, palette, indices);
  const postLevel = QUANTIZED_OXIPNG_LEVEL[mode];
  const recompressed = await oxipng(indexedPng, postLevel);
  return smallerOutput(indexedPng, recompressed);
}

async function optimizePng(bytes, mode) {
  if (mode === "quality") {
    return oxipng(bytes, OXIPNG_LEVEL.quality);
  }
  if (bytes.byteLength >= LOSSY_MIN_BYTES) {
    try {
      return await optimizePngLossy(bytes, mode);
    } catch (err) {
      console.warn("PNG 有损路径失败，回退无损", err);
      return oxipng(bytes, OXIPNG_LEVEL[mode]);
    }
  }
  return oxipng(bytes, OXIPNG_LEVEL[mode]);
}

async function optimizeJpg(bytes, mode) {
  const imageData = await jpegDecode(bytes);
  return jpegEncode(imageData, { quality: JPEG_QUALITY[mode] });
}

export async function optimizeFile(file, mode) {
  const started = performance.now();
  const format = detectFormat(file);
  if (!format) {
    return {
      name: file.name,
      status: "failed",
      message: "仅支持 PNG / JPG / JPEG",
      originalBytes: file.size,
      elapsedMs: Math.round(performance.now() - started),
    };
  }
  const originalBytes = new Uint8Array(await file.arrayBuffer());
  try {
    const optimized =
      format === "png"
        ? await optimizePng(originalBytes, mode)
        : await optimizeJpg(originalBytes, mode);
    const originalSize = originalBytes.byteLength;
    const optimizedSize = optimized.byteLength;
    if (optimizedSize >= originalSize) {
      return {
        name: file.name,
        status: "skipped",
        message: "压缩后体积未变小，已跳过",
        format,
        originalBytes: originalSize,
        optimizedBytes: optimizedSize,
        elapsedMs: Math.round(performance.now() - started),
      };
    }
    return {
      name: file.name,
      status: "optimized",
      format,
      originalBytes: originalSize,
      optimizedBytes: optimizedSize,
      optimizedBlob: new Blob([optimized], {
        type: format === "png" ? "image/png" : "image/jpeg",
      }),
      elapsedMs: Math.round(performance.now() - started),
    };
  } catch (err) {
    return {
      name: file.name,
      status: "failed",
      message: String(err?.message || err),
      format,
      originalBytes: originalBytes.byteLength,
      elapsedMs: Math.round(performance.now() - started),
    };
  }
}

export function downloadName(fileName, mode) {
  const dot = fileName.lastIndexOf(".");
  if (dot <= 0) return `${fileName}.${mode}.bin`;
  const base = fileName.slice(0, dot);
  const ext = fileName.slice(dot + 1);
  return `${base}.${mode}.${ext}`;
}
