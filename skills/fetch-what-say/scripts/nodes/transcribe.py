"""transcribe 节点:mlx-whisper 转写,产出 transcript.srt 与 transcript.txt。

audio.wav 用完即删。srt 已存在则跳过转写,只重生成 txt。
model/language 由 self.kwargs 注入。
"""

from __future__ import annotations

from pathlib import Path

from esflow import Node

from common import (
    CliError,
    EXIT_VALIDATION,
    log,
    write_srt,
    write_txt_from_srt,
)


class Transcribe(Node):
    id = "transcribe"
    title = "转写文字稿"

    def accept(self, ctx) -> bool:
        """上游 extract_audio 被跳过则本节点一并跳过。"""
        return ctx.get("extract_audio") is not None

    def run(self, ctx) -> dict:
        audio_path = ctx.get("extract_audio")["audio_path"]
        work_dir = Path(audio_path).parent
        srt_path = work_dir / "transcript.srt"
        txt_path = work_dir / "transcript.txt"

        if srt_path.exists():
            write_txt_from_srt(srt_path, txt_path)
            Path(audio_path).unlink(missing_ok=True)
            log(f"[transcribe] cached {srt_path}")
            return {"srt_path": str(srt_path), "txt_path": str(txt_path), "cached": True}

        try:
            import mlx_whisper
        except ImportError as exc:
            raise CliError("dependency_error", "缺少 Python 包:pip install mlx-whisper", EXIT_VALIDATION) from exc

        config = self.kwargs or {}
        model = config.get("model")
        language = config.get("language")
        kwargs = {"path_or_hf_repo": model} if model else {}
        if language:
            kwargs["language"] = language
        log(f"[transcribe] mlx-whisper model={model}")
        result = mlx_whisper.transcribe(str(audio_path), **kwargs)
        write_srt(result.get("segments", []), srt_path)
        write_txt_from_srt(srt_path, txt_path)
        Path(audio_path).unlink(missing_ok=True)
        return {"srt_path": str(srt_path), "txt_path": str(txt_path), "cached": False}

    def deliver(self, artifact) -> bool:
        return Path(artifact["srt_path"]).exists() and Path(artifact["txt_path"]).exists()
