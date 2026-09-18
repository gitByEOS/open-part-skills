"""切片 + faster-whisper，每句 fsync 追加到节点产物目录。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from common import (
    AUDIO_16K_NAME,
    CHUNK_DIR_NAME,
    PROGRESS_NAME,
    SRT_NAME,
    WHOLE_NAME,
    log,
)
from domain import CHUNK_SECONDS


def fmt_whole(t: float) -> str:
    return f"{t:09.2f}"


def fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def append_sync(handle, text: str) -> None:
    handle.write(text)
    handle.flush()
    os.fsync(handle.fileno())


def load_progress(path: Path) -> dict:
    if not path.exists():
        return {"last_completed_chunk": -1, "next_idx": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_16k(wav: Path, dest: Path, ffmpeg: str) -> Path:
    """降到 16kHz 单声道 s16le，给 whisper 省内存、免内部再重采样。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        log(f"复用 16k {dest.name} bytes={dest.stat().st_size}")
        return dest
    src_bytes = wav.stat().st_size
    log(f"转 16k mono {wav.name} bytes={src_bytes} → {dest.name}")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(wav),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True)
    if not dest.is_file() or dest.stat().st_size <= 0:
        raise RuntimeError("16k 转码失败")
    log(f"16k 完成 bytes={dest.stat().st_size}")
    return dest


def ensure_chunks(wav: Path, chunk_dir: Path, ffmpeg: str) -> list[Path]:
    chunk_dir.mkdir(exist_ok=True)
    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    if chunks:
        log(f"复用已有切片 {len(chunks)} 段")
        return chunks
    log(f"切片 {wav.name}")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(wav),
        "-f",
        "segment",
        "-segment_time",
        str(CHUNK_SECONDS),
        "-c",
        "copy",
        str(chunk_dir / "chunk_%03d.wav"),
    ]
    subprocess.run(cmd, check=True)
    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    if not chunks:
        raise RuntimeError("切片失败")
    return chunks


def cleanup_chunks(chunk_dir: Path) -> None:
    if not chunk_dir.is_dir():
        return
    shutil.rmtree(chunk_dir)
    log(f"已清理切片 {chunk_dir.name}")


def cleanup_process_wav(chunk_dir: Path, pcm_path: Path) -> None:
    """全文落盘后删除过程 wav；源文件不动。中断不走这里。"""
    cleanup_chunks(chunk_dir)
    if pcm_path.is_file():
        pcm_path.unlink()
        log(f"已清理 {pcm_path.name}")


def mark_done(progress_path: Path, progress: dict) -> None:
    write_json(
        progress_path,
        {
            "last_completed_chunk": int(progress.get("last_completed_chunk", -1)),
            "next_idx": int(progress.get("next_idx", 1)),
            "done": True,
        },
    )


def can_skip(progress: dict, whole_path: Path, chunk_dir: Path) -> bool:
    if not whole_path.is_file() or whole_path.stat().st_size <= 0:
        return False
    if progress.get("done"):
        return True
    chunks = sorted(chunk_dir.glob("chunk_*.wav")) if chunk_dir.is_dir() else []
    return bool(chunks) and is_complete(progress, len(chunks))


def is_complete(progress: dict, chunk_count: int) -> bool:
    if chunk_count <= 0:
        return False
    return int(progress.get("last_completed_chunk", -1)) >= chunk_count - 1


def load_whisper(runtime: dict):
    from faster_whisper import WhisperModel

    kwargs = {}
    if runtime.get("device"):
        kwargs["device"] = runtime["device"]
    if runtime.get("compute_type"):
        kwargs["compute_type"] = runtime["compute_type"]
    if runtime.get("download_root"):
        kwargs["download_root"] = runtime["download_root"]
    if runtime.get("model_is_local"):
        kwargs["local_files_only"] = True
    log(f"加载模型 {runtime['model']} kwargs={kwargs}")
    return WhisperModel(runtime["model"], **kwargs)


def transcribe_wav(wav: Path, out_dir: Path, runtime: dict, fresh: bool) -> dict:
    chunk_dir = out_dir / CHUNK_DIR_NAME
    pcm_path = out_dir / AUDIO_16K_NAME
    srt_path = out_dir / SRT_NAME
    whole_path = out_dir / WHOLE_NAME
    progress_path = out_dir / PROGRESS_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    if fresh:
        for path in (srt_path, whole_path, progress_path):
            if path.exists():
                path.unlink()
        log("fresh：清空旧稿后重跑")

    progress = load_progress(progress_path)
    if not fresh and can_skip(progress, whole_path, chunk_dir):
        log(f"已有完整合并稿，跳过识别 → {whole_path.name}")
        mark_done(progress_path, progress)
        cleanup_process_wav(chunk_dir, pcm_path)
        return {
            "srt": str(srt_path),
            "whole": str(whole_path),
            "progress": str(progress_path),
            "skipped": True,
            "sentences": int(progress.get("next_idx", 1)) - 1,
        }

    pcm = ensure_16k(wav, pcm_path, runtime["ffmpeg"])
    chunks = ensure_chunks(pcm, chunk_dir, runtime["ffmpeg"])

    start_chunk = progress["last_completed_chunk"] + 1
    idx = int(progress["next_idx"])
    total = len(chunks)
    log(f"共 {total} 段，CPU 上整场可能数十分钟；日志还在刷就没卡死")
    log(
        f"进度 {min(start_chunk + 1, total)}/{total} "
        f"从 chunk_{start_chunk:03d} 开始识别，已完成句数={idx - 1}"
    )
    model = load_whisper(runtime)

    with srt_path.open("a", encoding="utf-8") as srt_f, whole_path.open(
        "a", encoding="utf-8"
    ) as whole_f:
        for chunk_path in chunks:
            i = int(chunk_path.stem.split("_")[1])
            if i < start_chunk:
                continue
            offset = i * CHUNK_SECONDS
            log(f"开始识别 {chunk_path.name} {i + 1}/{total} offset={offset}")
            segments, info = model.transcribe(
                str(chunk_path),
                language="zh",
                condition_on_previous_text=False,
            )
            duration = float(info.duration or 0.0)
            log(
                f"语言={info.language} 概率={info.language_probability:.3f} 时长={duration:.2f}"
            )
            n = 0
            for seg in segments:
                if duration and seg.start >= duration:
                    log(f"  截断幻觉 start={seg.start:.2f} >= {duration:.2f}")
                    break
                end_in_chunk = min(seg.end, duration) if duration else seg.end
                start = seg.start + offset
                end = end_in_chunk + offset
                text = (seg.text or "").strip()
                if not text:
                    continue
                append_sync(
                    whole_f, f"[{fmt_whole(start)}-{fmt_whole(end)}] {text}\n"
                )
                append_sync(
                    srt_f,
                    f"{idx}\n{fmt_srt(start)} --> {fmt_srt(end)}\n{text}\n\n",
                )
                log(f"  {fmt_whole(start)}-{fmt_whole(end)} {text}")
                idx += 1
                n += 1
            write_json(
                progress_path,
                {"last_completed_chunk": i, "next_idx": idx},
            )
            log(f"完成 {chunk_path.name} {i + 1}/{total} 本段句数={n} 累计句数={idx - 1}")

    log(f"写入完成 共 {idx - 1} 句 → {srt_path.name}")
    mark_done(progress_path, {"last_completed_chunk": total - 1, "next_idx": idx})
    cleanup_process_wav(chunk_dir, pcm_path)
    return {
        "srt": str(srt_path),
        "whole": str(whole_path),
        "progress": str(progress_path),
        "skipped": False,
        "sentences": idx - 1,
    }
