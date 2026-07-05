"""resolve 节点:解析 input/cookies,算 media_id,建 work_dir,产出 plan。

CLI 参数由 Runner.load(node_args=...) 注入到 self.kwargs,
本节点读 self.kwargs,完成输入解析与工作目录准备。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from esflow import Node

from common import (
    CliError,
    DEFAULT_OUTPUT_DIR,
    EXIT_RUNTIME,
    log,
    resolve_cookies,
    resolve_input,
    safe_id,
)


class Resolve(Node):
    id = "resolve"
    title = "解析输入与工作目录"

    def run(self, ctx) -> dict:
        args = self.kwargs or {}
        kind, resolved = resolve_input(args["input"])
        cookies = resolve_cookies(args.get("cookies"), resolved if kind == "url" else None)
        media_id = safe_id(resolved.stem) if kind == "file" else self._fetch_media_id(resolved, cookies)
        work_dir = Path(args.get("out") or DEFAULT_OUTPUT_DIR).expanduser() / media_id
        work_dir.mkdir(parents=True, exist_ok=True)

        plan = {
            "input_kind": kind,
            "resolved": str(resolved),
            "id": media_id,
            "work_dir": str(work_dir),
            "cookies": str(cookies) if cookies else None,
        }
        log(f"[resolve] kind={kind} id={media_id} work_dir={work_dir}")
        return plan

    def _fetch_media_id(self, url, cookies):
        """URL 输入走 yt-dlp 取 id;本地文件由调用方用 stem。"""
        command = ["yt-dlp", "--no-playlist", "--skip-download", "--dump-single-json"]
        if cookies:
            command.extend(["--cookies", str(cookies)])
        command.append(url)
        log(f"[metadata] {url}")
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
        if result.returncode != 0:
            raise CliError("metadata_error", f"yt-dlp 读取元数据失败,exit={result.returncode}", EXIT_RUNTIME, True)
        try:
            metadata = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CliError("metadata_error", "yt-dlp 元数据不是有效 JSON", EXIT_RUNTIME, True) from exc
        media_id = metadata.get("id") or metadata.get("display_id")
        if not media_id:
            raise CliError("metadata_error", "yt-dlp 元数据缺少 id", EXIT_RUNTIME, True)
        return safe_id(str(media_id))
