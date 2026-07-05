"""extract_audio 节点:ffmpeg 把 video 提取为 16k 单声道 wav,供 mlx-whisper 转写。

work_dir 从上游 download 的 video_path 推导,不依赖 resolve。
transcribe 开关由 self.kwargs 注入(--no-transcribe 时 accept 返回 False,下游级联跳过)。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_RUNTIME, log


class ExtractAudio(Node):
    id = "extract_audio"
    title = "提取音频"

    def accept(self, ctx) -> bool:
        """--no-transcribe 时跳过本节点及下游 transcribe/export_html。"""
        return bool((self.kwargs or {}).get("transcribe", True))

    def run(self, ctx) -> dict:
        video_path = ctx.get("download")["video_path"]
        work_dir = Path(video_path).parent
        audio = work_dir / "audio.wav"
        if audio.exists():
            log(f"[audio] cached {audio}")
            return {"audio_path": str(audio)}

        log(f"[audio] extract {video_path} -> {audio}")
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-y", "-i", str(video_path),
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                str(audio),
            ],
            stdout=sys.stderr,
            stderr=sys.stderr,
            env={**os.environ, "LC_ALL": "C"},
        )
        if result.returncode != 0:
            raise CliError("audio_error", f"ffmpeg 提取音频失败,exit={result.returncode}", EXIT_RUNTIME)
        return {"audio_path": str(audio)}

    def deliver(self, artifact) -> bool:
        return Path(artifact["audio_path"]).exists()
