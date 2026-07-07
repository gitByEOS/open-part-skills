"""match 节点:ASR 对齐非 N.mp3 命名的音频,重命名为 N.mp3。

条件节点:audio/ 存在非 `N.ext` 命名的音频时才跑,否则 accept False 跳过,
merge 直读 gen.audio_dir。依赖 onnxruntime/numpy(备选重依赖)。
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from esflow import Node

import narrator_core
from common import CliError, EXIT_RUNTIME, load_srt_texts, log


_NAMED_PATTERN = re.compile(r"^\d+\.(mp3|wav|m4a|ogg)$")
_AUDIO_GLOBS = ("*.mp3", "*.wav", "*.m4a")


def _has_unnamed(audio_dir: Path) -> bool:
    for glob in _AUDIO_GLOBS:
        for f in audio_dir.glob(glob):
            if not _NAMED_PATTERN.match(f.name):
                return True
    return False


def _normalize(text: str) -> str:
    return re.sub(r"[^\w一-鿿]", "", text).lower()


def _match_text(asr_text: str, texts: list[str]) -> tuple[int, float]:
    asr_norm = _normalize(asr_text)
    scores = [
        0 if not text else difflib.SequenceMatcher(None, asr_norm, _normalize(text)).ratio()
        for text in texts
    ]
    best_idx = max(range(len(scores)), key=lambda i: scores[i])
    return best_idx + 1, scores[best_idx]


class Match(Node):
    id = "match"
    title = "ASR 对齐音频段号"

    def accept(self, ctx) -> bool:
        split = ctx.get("split")
        if split is None:
            return False
        return _has_unnamed(Path(split["audio_dir"]))

    def run(self, ctx) -> dict:
        try:
            import onnxruntime as ort
        except ImportError:
            raise CliError(
                "no_onnxruntime",
                "match 需要 onnxruntime/numpy,pip install onnxruntime numpy",
                EXIT_RUNTIME,
            )

        split = ctx.get("split")
        audio_dir = Path(split["audio_dir"])
        srt_file = Path(split["srt_path"])
        texts = load_srt_texts(srt_file)

        audio_files = []
        for glob in _AUDIO_GLOBS:
            audio_files.extend(sorted(audio_dir.glob(glob)))
        if not audio_files:
            log("[match] 无音频文件,跳过")
            return {"renamed": 0}

        model_path = narrator_core.MODEL_DIR / "model.int8.onnx"
        tokens_path = narrator_core.MODEL_DIR / "tokens.json"
        cmvn_path = narrator_core.MODEL_DIR / "am.mvn"
        narrator_core.ensure_model_files(model_path, tokens_path, cmvn_path)

        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        meta = narrator_core.load_meta(session, cmvn_path)
        tokens = narrator_core.load_tokens(tokens_path)

        log(f"[match] 段数={len(texts)} 音频={len(audio_files)}")
        matches: dict[Path, int] = {}
        for audio_file in audio_files:
            log(f"  识别:{audio_file.name}")
            waveform = narrator_core.read_audio(audio_file)
            asr_text = narrator_core.transcribe(session, meta, tokens, waveform, "zh", True)
            idx, score = _match_text(asr_text, texts)
            if score < 0.3:
                log(f"  ⚠️ 置信度低 ({score:.2f}),跳过")
                continue
            matches[audio_file] = idx
            display = texts[idx - 1][:40] if texts[idx - 1] else "⚪"
            log(f"  → [{idx}] {display} (score={score:.2f})")

        renamed = 0
        for audio_file, idx in matches.items():
            ext = audio_file.suffix.lstrip(".")
            new_path = audio_dir / f"{idx}.{ext}"
            if new_path.exists() and new_path != audio_file:
                log(f"  ⚠️ {new_path.name} 已存在,跳过")
            else:
                audio_file.rename(new_path)
                renamed += 1
                log(f"  {audio_file.name} → {new_path.name}")
        log(f"[match] 重命名 {renamed} 个")
        return {"renamed": renamed}

    def deliver(self, artifact) -> bool:
        return bool(artifact and "renamed" in artifact)
