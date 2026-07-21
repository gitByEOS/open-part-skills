#!/usr/bin/env python3
"""Generate one MP3 voice reply with edge-tts."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import re
import subprocess
import sys
import tempfile


VOICE_ALIASES = {
    "xiaoxiao": ("zh-CN-XiaoxiaoNeural", "-6Hz"),
    "xiaoyi": ("zh-CN-XiaoyiNeural", "+7Hz"),
}
MAX_TEXT_LENGTH = 20_000


def split_for_tts(text: str, max_len: int = 350) -> list[str]:
    text = text.strip()
    if len(text) <= max_len:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        if end == len(text):
            chunks.append(text[start:].strip())
            break
        boundary = -1
        for character in "\n。！？；.!?;":
            boundary = max(boundary, text.rfind(character, start, end))
        if boundary <= start:
            for character in "，, ":
                boundary = max(boundary, text.rfind(character, start, end))
        if boundary <= start:
            boundary = end - 1
        chunks.append(text[start : boundary + 1].strip())
        start = boundary + 1
    return [chunk for chunk in chunks if chunk]


def percent(value: float) -> str:
    amount = round((value - 1) * 100)
    return f"{amount:+d}%"


def read_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        text = args.text
    elif args.text_file is not None:
        text = args.text_file.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise ValueError("provide --text, --text-file, or text on stdin")
    text = re.sub(r"<(?:qqmedia|qqfile|qqimg|qqvoice|qqvideo)>[\s\S]*?</(?:qqmedia|qqfile|qqimg|qqvoice|qqvideo)>", "", text, flags=re.I).strip()
    if not text:
        raise ValueError("spoken text is empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"spoken text exceeds {MAX_TEXT_LENGTH} characters")
    return text


def run_ffmpeg(command: list[str], error_message: str) -> None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise RuntimeError("ffmpeg is required for audio post-processing") from error
    if result.returncode != 0:
        detail = result.stderr.strip()
        raise RuntimeError(f"{error_message}: {detail}" if detail else error_message)


def add_tail_silence(source: Path, output: Path, seconds: float) -> None:
    if seconds == 0:
        source.replace(output)
        return
    with tempfile.TemporaryDirectory(dir=output.parent, prefix="voice-to-me-") as directory:
        workspace = Path(directory)
        silence = workspace / "silence.mp3"
        manifest = workspace / "concat.txt"
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{seconds:g}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "48k",
            str(silence),
        ]
        try:
            run_ffmpeg(command, "ffmpeg could not create trailing silence")
            manifest.write_text(f"file '{source}'\nfile '{silence}'\n", encoding="utf-8")
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(manifest),
                    "-c",
                    "copy",
                    str(output),
                ],
                "ffmpeg could not append trailing silence",
            )
        finally:
            source.unlink(missing_ok=True)


def apply_denoise(source: Path, output: Path) -> None:
    try:
        run_ffmpeg(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-af",
                "highpass=f=80,deesser=i=0.18:m=0.35:f=0.5,lowpass=f=10000",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "64k",
                str(output),
            ],
            "ffmpeg could not apply light denoise",
        )
    finally:
        source.unlink(missing_ok=True)


async def generate(
    text: str,
    output: Path,
    voice: str,
    pitch: str,
    rate: float,
    tail_silence: float,
    denoise: bool,
) -> int:
    try:
        import edge_tts
    except ImportError as error:
        raise RuntimeError("edge-tts is not installed in this Python environment") from error

    output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".mp3", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            for chunk in split_for_tts(text):
                communicator = edge_tts.Communicate(chunk, voice, rate=percent(rate), pitch=pitch)
                received = False
                async for part in communicator.stream():
                    if part["type"] == "audio":
                        data = part["data"]
                        temporary.write(data)
                        total += len(data)
                        received = True
                if not received:
                    raise RuntimeError("TTS service returned no audio")
            temporary.flush()
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    if total == 0:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError("TTS service returned an empty audio file")
    if denoise:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".mp3", delete=False) as cleaned:
            cleaned_path = Path(cleaned.name)
        apply_denoise(temporary_path, cleaned_path)
        add_tail_silence(cleaned_path, output, tail_silence)
    else:
        add_tail_silence(temporary_path, output, tail_silence)
    return output.stat().st_size


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="text to speak")
    source.add_argument("--text-file", type=Path, help="UTF-8 text file to speak")
    parser.add_argument("--output", type=Path, required=True, help="destination .mp3 file")
    parser.add_argument("--voice", choices=sorted(VOICE_ALIASES), default="xiaoyi")
    parser.add_argument("--rate", type=float, default=1.13, help="speech rate from 0.5 to 2.0")
    parser.add_argument("--tail-silence", type=float, default=0.5, help="trailing silence in seconds from 0 to 5")
    parser.add_argument(
        "--denoise",
        dest="denoise",
        action="store_true",
        default=True,
        help="enable light high-pass, de-essing, and low-pass filters (default)",
    )
    parser.add_argument(
        "--no-denoise",
        dest="denoise",
        action="store_false",
        help="disable light audio denoise",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.suffix.lower() != ".mp3":
        raise ValueError("--output must end in .mp3")
    if not 0.5 <= args.rate <= 2.0:
        raise ValueError("--rate must be between 0.5 and 2.0")
    if not 0 <= args.tail_silence <= 5:
        raise ValueError("--tail-silence must be between 0 and 5 seconds")
    text = read_text(args)
    voice, pitch = VOICE_ALIASES[args.voice]
    output = args.output.expanduser().resolve()
    size = asyncio.run(generate(text, output, voice, pitch, args.rate, args.tail_silence, args.denoise))
    print(output)
    print(f"generated {size} bytes with {voice}; trailing silence {args.tail_silence:g}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"voice_to_me: {error}", file=sys.stderr)
        raise SystemExit(1)
