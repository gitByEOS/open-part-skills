"""wav 解析与会议落盘文件名。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from common import CliError, EXIT_VALIDATION

DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")
CHUNK_SECONDS = 300


def resolve_wav(path: Path) -> Path:
    """用户给 wav 就用；给目录则必须恰好一个 wav。"""
    if path.is_file() and path.suffix.lower() == ".wav":
        return path
    if not path.is_dir():
        raise CliError("invalid_path", f"不是 wav 也不是目录：{path}", EXIT_VALIDATION)
    wavs = sorted(p for p in path.glob("*.wav") if p.is_file())
    if len(wavs) == 1:
        return wavs[0]
    names = " ".join(p.name for p in wavs) or "(无)"
    raise CliError("invalid_path", f"需要唯一 wav，当前：{names}", EXIT_VALIDATION)


def meet_filename(wav: Path, explicit: str | None) -> str:
    """指定名 → 路径里第一段日期 → wav mtime。"""
    if explicit:
        name = Path(explicit).name
        return name if name.endswith(".md") else f"{name}.md"
    for part in wav.resolve().parts:
        match = DATE_RE.search(part)
        if match:
            return f"meet-{match.group(1)}-{match.group(2)}-{match.group(3)}.md"
    local = datetime.fromtimestamp(wav.stat().st_mtime).astimezone()
    return f"meet-{local:%Y-%m-%d}.md"
