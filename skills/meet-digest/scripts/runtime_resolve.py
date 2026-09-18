"""读 scripts/local.py，发现 ffmpeg 与本地 faster-whisper。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from common import CliError, EXIT_VALIDATION, log
from local_load import local_path, runtime_cfg


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def default_hub_cache() -> Path:
    env = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "huggingface" / "hub"


def _is_ct2_dir(path: Path) -> bool:
    return path.is_dir() and (path / "model.bin").is_file()


def _repo_size(path: Path) -> str:
    for parent in (path, *path.parents):
        name = parent.name
        prefix = "models--Systran--faster-whisper-"
        if name.startswith(prefix):
            return name[len(prefix) :]
    return path.name


def discover_models(root: Path) -> dict[str, Path]:
    """尺寸名 → 最新 snapshot。"""
    found: dict[str, Path] = {}
    if not root.exists():
        return found
    if _is_ct2_dir(root):
        found[_repo_size(root)] = root
        return found
    for repo in root.glob("models--Systran--faster-whisper-*"):
        snapshots = repo / "snapshots"
        if not snapshots.is_dir():
            continue
        snaps = [p for p in snapshots.iterdir() if _is_ct2_dir(p)]
        if not snaps:
            continue
        latest = max(snaps, key=lambda p: p.stat().st_mtime)
        found[_repo_size(repo)] = latest
    return found


def _ffmpeg_candidates(cfg_ffmpeg: str) -> list[str]:
    candidates = []
    if cfg_ffmpeg:
        candidates.append(cfg_ffmpeg)
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(which)
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            candidates.append(exe)
    except Exception:
        pass
    return candidates


def pick_ffmpeg(cfg_ffmpeg: str) -> str:
    for item in _ffmpeg_candidates(cfg_ffmpeg):
        path = Path(item).expanduser()
        if path.is_file():
            log(f"ffmpeg={path}")
            return str(path)
    raise CliError(
        "ffmpeg_missing",
        "找不到 ffmpeg。请安装并加入 PATH，或在 local.py 填写 FFMPEG，或 pip install imageio-ffmpeg",
        EXIT_VALIDATION,
    )


def pick_model(cfg: dict, download_root: Path) -> tuple[str, bool]:
    """返回 (WhisperModel 第一参, 是否本地路径)。尺寸名且缓存没有才下载。"""
    pinned = _text(cfg.get("model"))
    discovered = discover_models(download_root)
    log(f"发现本地模型 {sorted(discovered)}")

    if pinned:
        pin_path = Path(pinned).expanduser()
        if pin_path.exists():
            resolved = pin_path.resolve()
            if not _is_ct2_dir(resolved):
                raise CliError(
                    "model_invalid",
                    f"model 路径不是 CTranslate2 目录（缺 model.bin）：{resolved}",
                    EXIT_VALIDATION,
                )
            return str(resolved), True
        if pinned in discovered:
            return str(discovered[pinned]), True
        log(f"本地无 {pinned}，允许 WhisperModel 按尺寸名下载")
        return pinned, False

    if len(discovered) == 1:
        size, path = next(iter(discovered.items()))
        log(f"使用唯一本地模型 {size} → {path}")
        return str(path), True
    if len(discovered) == 0:
        raise CliError(
            "model_missing",
            "未发现本地 faster-whisper。"
            "在 local.py 填写 MODEL：CT2 目录，或尺寸名 tiny / base / small / medium / large-v3。"
            f"尺寸名且本地没有时按该名下载。扫描根 {download_root}",
            EXIT_VALIDATION,
        )
    names = ", ".join(sorted(discovered))
    raise CliError(
        "model_ambiguous",
        f"发现多个本地模型：{names}。在 local.py 填写 MODEL 指定其中一个",
        EXIT_VALIDATION,
    )


def resolve_runtime(skill_dir: Path) -> dict:
    skill = Path(skill_dir).resolve()
    if local_path().parent.parent != skill:
        raise CliError(
            "runtime_invalid",
            f"local.py 不在该 skill 的 scripts 下:{skill}",
            EXIT_VALIDATION,
        )
    cfg = runtime_cfg()
    download_root_text = _text(cfg.get("download_root"))
    download_root = (
        Path(download_root_text).expanduser().resolve()
        if download_root_text
        else default_hub_cache()
    )
    ffmpeg = pick_ffmpeg(_text(cfg.get("ffmpeg")))
    model, is_local = pick_model(cfg, download_root)
    device = _text(cfg.get("device"))
    compute_type = _text(cfg.get("compute_type"))
    return {
        "ffmpeg": ffmpeg,
        "download_root": str(download_root),
        "model": model,
        "model_is_local": is_local,
        "device": device,
        "compute_type": compute_type,
        "runtime_path": str(local_path()),
    }
