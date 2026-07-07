"""gen 节点:Edge TTS 分段合成 audio/N.mp3。

依赖 split。voice/rate 来自 kwargs。空段跳过。
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_VALIDATION, load_srt_texts, log


EDGE_TTS_VOICES = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "xiaoyi": "zh-CN-XiaoyiNeural",
}

EDGE_TTS_PITCH = {
    "xiaoxiao": "-6Hz",
    "xiaoyi": "-10Hz",
}


def _split_for_tts(text: str, max_len: int = 350) -> list[str]:
    """超长段按句号/逗号边界切分,控制在 max_len 内。"""
    if len(text) <= max_len:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        if end >= len(text):
            chunks.append(text[start:])
            break
        boundary = -1
        for ch in "\n。！？；.!?;":
            pos = text.rfind(ch, start, end)
            if pos > start:
                boundary = max(boundary, pos)
        if boundary > start:
            chunks.append(text[start : boundary + 1])
            start = boundary + 1
            continue
        for ch in "，, ":
            pos = text.rfind(ch, start, end)
            if pos > start:
                boundary = max(boundary, pos)
        if boundary > start:
            chunks.append(text[start : boundary + 1])
            start = boundary + 1
        else:
            chunks.append(text[start:end])
            start = end
    return chunks


async def _generate_audio(texts, voice, rate, pitch, audio_dir: Path) -> int:
    import edge_tts

    count = 0
    for index, text in enumerate(texts, 1):
        if not re.search(r"[a-zA-Z一-鿿0-9]", text):
            log(f"  [{index}] ⚪ 跳过空行")
            continue

        audio_parts = []
        for chunk in _split_for_tts(text):
            try:
                comm = edge_tts.Communicate(
                    chunk, voice, rate=f"+{round((rate - 1) * 100)}%", pitch=pitch
                )
                part_chunks = []
                async for part in comm.stream():
                    if part["type"] == "audio":
                        part_chunks.append(part["data"])
                if part_chunks:
                    audio_parts.append(b"".join(part_chunks))
            except Exception as exc:
                log(f"  [{index}] ⚠️ 失败:{exc}")

        if audio_parts:
            combined = b"".join(audio_parts)
            (audio_dir / f"{index}.mp3").write_bytes(combined)
            count += 1
            display = text[:40] + "..." if len(text) > 40 else text
            log(f"  [{index}] {index}.mp3 ({len(combined)} bytes) - {display}")
        else:
            log(f"  [{index}] ⚠️ 无音频")
    return count


class Gen(Node):
    id = "gen"
    title = "Edge TTS 分段配音"

    def accept(self, ctx) -> bool:
        return ctx.get("split") is not None

    def run(self, ctx) -> dict:
        split = ctx.get("split")
        kw = self.kwargs or {}
        voice_name = kw.get("voice", "xiaoxiao")
        if voice_name not in EDGE_TTS_VOICES:
            raise CliError(
                "bad_voice",
                f"--voice 仅支持:{', '.join(EDGE_TTS_VOICES)}",
                EXIT_VALIDATION,
            )
        try:
            rate = float(kw.get("rate", 1.175))
        except ValueError:
            raise CliError("bad_rate", "--rate 需要数字", EXIT_VALIDATION)

        audio_dir = Path(split["audio_dir"])
        srt_file = Path(split["srt_path"])
        texts = load_srt_texts(srt_file)

        log(f"[gen] 段数={len(texts)} 音色={voice_name} 速率={rate}")
        count = asyncio.run(
            _generate_audio(texts, EDGE_TTS_VOICES[voice_name], rate, EDGE_TTS_PITCH[voice_name], audio_dir)
        )
        log(f"[gen] 完成,生成 {count} 个音频")
        return {"audio_dir": str(audio_dir), "count": count, "segment_count": len(texts)}

    def deliver(self, artifact) -> bool:
        return bool(artifact and Path(artifact["audio_dir"]).is_dir())
