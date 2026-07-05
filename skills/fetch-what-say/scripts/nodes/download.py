"""download 节点:URL 走 yt-dlp 下载,本地文件复制到 work_dir/video.<ext>。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from esflow import Node

from common import CliError, EXIT_RUNTIME, EXIT_VALIDATION, log


def _existing_video(work_dir):
    videos = [
        path for path in work_dir.glob("video.*")
        if path.stem == "video" and path.suffix != ".part"
    ]
    return sorted(videos)[0] if videos else None


def _build_download_command(url, work_dir, cookies, height, prefer, merge_format):
    sort = "+size" if prefer == "size" else "br"
    command = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format",
        merge_format,
        "-f",
        "bv*+ba/b",
        "-S",
        f"res:{height},hdr:SDR,{sort}",
        "-o",
        str(work_dir / "video.%(ext)s"),
    ]
    if cookies:
        command.extend(["--cookies", str(cookies)])
    command.append(url)
    return command


def _check_download_dependencies():
    missing = [name for name in ("yt-dlp", "ffmpeg") if not shutil.which(name)]
    if missing:
        raise CliError("dependency_error", "缺少依赖:" + ", ".join(missing), EXIT_VALIDATION)


class Download(Node):
    id = "download"
    title = "下载或复制媒体"

    def run(self, ctx) -> dict:
        plan = ctx.get("resolve")
        work_dir = Path(plan["work_dir"])
        kind = plan["input_kind"]
        resolved = plan["resolved"]
        config = self.kwargs or {}
        height = config.get("height", 360)
        prefer = config.get("prefer", "size")
        merge_format = config.get("merge_format", "mp4")

        if kind == "file":
            src = Path(resolved)
            target = work_dir / f"video{src.suffix}"
            if target.exists():
                log(f"[download] cached {target}")
                return {"video_path": str(target), "cached": True}
            shutil.copy2(src, target)
            log(f"[download] copy {src} -> {target}")
            return {"video_path": str(target), "cached": False}

        _check_download_dependencies()
        cached = _existing_video(work_dir)
        if cached:
            log(f"[download] cached {cached}")
            return {"video_path": str(cached), "cached": True}

        cookies = plan.get("cookies")
        command = _build_download_command(resolved, work_dir, cookies, height, prefer, merge_format)
        auth_state = f"cookies={cookies}" if cookies else "cookies=none"
        log(f"[download] {resolved} (<= {height}p, prefer SDR/{prefer}, {auth_state})")
        result = subprocess.run(command, stdout=sys.stderr, stderr=sys.stderr, env={**os.environ, "LC_ALL": "C"})
        if result.returncode != 0:
            raise CliError("download_error", f"yt-dlp 下载失败,exit={result.returncode}", EXIT_RUNTIME, True)

        video = _existing_video(work_dir)
        if not video:
            raise CliError("download_error", "yt-dlp 没有产出 video 文件", EXIT_RUNTIME, True)
        return {"video_path": str(video), "cached": False}

    def deliver(self, artifact) -> bool:
        return Path(artifact["video_path"]).exists()
