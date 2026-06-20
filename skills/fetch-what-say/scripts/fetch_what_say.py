#!/usr/bin/env python3
"""抓取 yt-dlp 支持的媒体，并提取总结友好的文字稿。"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from html import escape
from pathlib import Path
from urllib.parse import urlparse


SCHEMA_VERSION = "1.0.0"
EXIT_OK, EXIT_RUNTIME, EXIT_AUTH, EXIT_VALIDATION = 0, 1, 2, 3
DEFAULT_WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "fetch-what-say"
DEFAULT_COOKIES_DIR = DEFAULT_OUTPUT_DIR / "cookies"
CIRCLE_NUMBER_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #fafafa;
            --surface: #f5f5f5;
            --surface-soft: #f2f3f5;
            --reader-bg: #fffefd;
            --reader-border: #e6dfd5;
            --text: #1a1a1a;
            --muted: #666;
            --accent: #0066cc;
            --border: #e0e0e0;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #1a1a1a;
                --surface: #252525;
                --surface-soft: #222427;
                --reader-bg: #202020;
                --reader-border: #38352f;
                --text: #e8e8e8;
                --muted: #999;
                --accent: #4d9fff;
                --border: #333;
            }}
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            line-height: 1.8;
            padding: 2rem 1rem;
        }}
        .container {{
            max-width: 760px;
            margin: 0 auto;
        }}
        .header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        h1 {{
            margin: 0 0 0.5rem;
            font-size: 1.5rem;
            line-height: 1.35;
            font-weight: 600;
        }}
        .meta {{
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .tabs {{
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }}
        .tab {{
            border: none;
            background: var(--surface);
            color: var(--muted);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
        }}
        .tab.active {{
            background: var(--accent);
            color: white;
        }}
        .content {{
            background: var(--surface);
            border-radius: 12px;
            padding: 2rem;
        }}
        .panel {{
            display: none;
        }}
        .panel.active {{
            display: block;
        }}
        .tree-view {{
            font-family: Menlo, Monaco, "Cascadia Mono", "Courier New", monospace;
            font-size: 0.9375rem;
            line-height: 1.3;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            margin: 0;
            color: var(--text);
        }}
        .tree-title,
        .section-title {{
            font-weight: 700;
        }}
        .tree-title {{
            font-size: 1.05rem;
        }}
        .has-index {{
            color: var(--accent);
            font-weight: 700;
        }}
        .transcript {{
            max-width: 760px;
            margin: 0 auto;
            padding: 1rem 1.1rem;
            border: 1px solid var(--reader-border);
            border-radius: 10px;
            background: var(--reader-bg);
            font-size: 1rem;
            line-height: 1.95;
            letter-spacing: 0.01em;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            color: var(--text);
            font-family: inherit;
        }}
        .empty-state {{
            padding: 3rem 1rem;
            text-align: center;
            color: var(--muted);
        }}
        @media (max-width: 640px) {{
            body {{
                padding: 1rem 0.75rem;
            }}
            .content {{
                padding: 1.25rem;
            }}
            .tree-view {{
                font-size: 0.875rem;
            }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <header class="header">
            <h1>{title}</h1>
            <div class="meta">{meta}</div>
        </header>
        <nav class="tabs">
            {tabs}
        </nav>
        <section class="content">
            {panels}
        </section>
    </main>
    <script>
        function switchTab(name) {{
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            document.getElementById('panel-' + name).classList.add('active');
        }}
    </script>
</body>
</html>
'''


class CliError(Exception):
    """带稳定错误码的 CLI 异常。"""

    def __init__(self, code, message, exit_code=EXIT_RUNTIME, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable


def log(message):
    print(message, file=sys.stderr, flush=True)


def safe_id(value):
    return re.sub(r"\W+", "_", value).strip("_")[-80:] or "media"


def resolve_input(value):
    value = value.strip()
    path = Path(value).expanduser()
    if path.is_file():
        return "file", path
    if value.startswith(("http://", "https://")):
        return "url", value
    raise CliError("validation_error", f"必须传入完整 URL 或本地文件：{value}", EXIT_VALIDATION)


def copy_cookies_to_store(source_path):
    """将用户提供的 cookies 复制到统一存储目录，便于后续复用。"""
    DEFAULT_COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    target = DEFAULT_COOKIES_DIR / source_path.name
    if not target.exists() or source_path.stat().st_mtime > target.stat().st_mtime:
        shutil.copy2(source_path, target)
        log(f"[cookies] 已复制到 {target}")
    return target


def stored_cookies():
    if not DEFAULT_COOKIES_DIR.exists():
        return []
    return [path for path in DEFAULT_COOKIES_DIR.glob("*.txt") if path.is_file()]


def cookie_domain_tokens(url):
    hostname = urlparse(url).hostname or ""
    return [part for part in hostname.lower().split(".") if part and part not in {"www", "com", "cn", "net", "org"}]


def resolve_cookies(explicit_path, resolved_input=None):
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.exists():
            raise CliError("auth_error", f"cookies 文件不存在：{path}", EXIT_AUTH)
        copy_cookies_to_store(path)
        return path
    if not isinstance(resolved_input, str) or not resolved_input.startswith(("http://", "https://")):
        return None
    tokens = cookie_domain_tokens(resolved_input)
    matches = [
        path for path in stored_cookies()
        if any(token in path.stem.lower() for token in tokens)
    ]
    if not matches:
        return None
    selected = max(matches, key=lambda path: path.stat().st_mtime)
    log(f"[cookies] 使用默认 cookies：{selected}")
    return selected


def check_download_dependencies():
    missing = [name for name in ("yt-dlp", "ffmpeg") if not shutil.which(name)]
    if missing:
        raise CliError("dependency_error", "缺少依赖：" + ", ".join(missing), EXIT_VALIDATION)


def build_metadata_command(url, cookies):
    command = [
        "yt-dlp",
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
    ]
    if cookies:
        command.extend(["--cookies", str(cookies)])
    command.append(url)
    return command


def fetch_media_id(url, cookies):
    log(f"[metadata] {url}")
    result = subprocess.run(
        build_metadata_command(url, cookies),
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode != 0:
        raise CliError("metadata_error", f"yt-dlp 读取元数据失败，exit={result.returncode}", EXIT_RUNTIME, True)
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CliError("metadata_error", "yt-dlp 元数据不是有效 JSON", EXIT_RUNTIME, True) from exc
    media_id = metadata.get("id") or metadata.get("display_id")
    if not media_id:
        raise CliError("metadata_error", "yt-dlp 元数据缺少 id", EXIT_RUNTIME, True)
    return safe_id(str(media_id))


def existing_video(work_dir):
    videos = [
        path for path in work_dir.glob("video.*")
        if path.stem == "video" and path.suffix != ".part"
    ]
    return sorted(videos)[0] if videos else None


def build_download_command(url, work_dir, cookies, height, prefer, merge_format):
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


def stage_download(url, work_dir, cookies, height, prefer, merge_format):
    work_dir.mkdir(parents=True, exist_ok=True)
    cached = existing_video(work_dir)
    if cached:
        return cached, True

    command = build_download_command(url, work_dir, cookies, height, prefer, merge_format)
    auth_state = f"cookies={cookies}" if cookies else "cookies=none"
    log(f"[download] {url} (<= {height}p, prefer SDR/{prefer}, {auth_state})")
    result = subprocess.run(command, stdout=sys.stderr, stderr=sys.stderr, env={**os.environ, "LC_ALL": "C"})
    if result.returncode != 0:
        raise CliError("download_error", f"yt-dlp 下载失败，exit={result.returncode}", EXIT_RUNTIME, True)

    video = existing_video(work_dir)
    if not video:
        raise CliError("download_error", "yt-dlp 没有产出 video 文件", EXIT_RUNTIME, True)
    return video, False


def srt_timestamp(seconds):
    total_ms = max(0, int(round(float(seconds) * 1000)))
    total_seconds, ms = divmod(total_ms, 1000)
    minutes_total, second = divmod(total_seconds, 60)
    hour, minute = divmod(minutes_total, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d},{ms:03d}"


def write_srt(segments, subtitle_path):
    lines = []
    index = 1
    for segment in segments:
        text = re.sub(r"\s+", " ", segment.get("text", "")).strip()
        if not text:
            continue
        lines.extend([
            str(index),
            f"{srt_timestamp(segment['start'])} --> {srt_timestamp(segment['end'])}",
            text,
            "",
        ])
        index += 1
    subtitle_path.write_text("\n".join(lines), encoding="utf-8")


def is_tail_noise(text):
    return not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text)


def write_txt_from_srt(subtitle_path, transcript_path):
    lines = []
    blocks = re.split(r"\n\s*\n", subtitle_path.read_text(encoding="utf-8").strip())
    for block in blocks:
        parts = [line.strip() for line in block.splitlines() if line.strip()]
        payload = [line for line in parts if not line.isdigit() and "-->" not in line]
        text = " ".join(payload)
        if text and not is_tail_noise(text):
            lines.append(text)
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stage_extract_audio(video, work_dir):
    audio = work_dir / "audio.wav"
    if audio.exists():
        return audio

    log(f"[audio] extract {video} -> {audio}")
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio),
        ],
        stdout=sys.stderr,
        stderr=sys.stderr,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode != 0:
        raise CliError("audio_error", f"ffmpeg 提取音频失败，exit={result.returncode}")
    return audio


def stage_transcribe(video, work_dir, model, language):
    outputs = {
        "srt": work_dir / "transcript.srt",
        "txt": work_dir / "transcript.txt",
    }
    if outputs["srt"].exists():
        write_txt_from_srt(outputs["srt"], outputs["txt"])
        (work_dir / "audio.wav").unlink(missing_ok=True)
        return outputs, True

    try:
        import mlx_whisper
    except ImportError as exc:
        raise CliError("dependency_error", "缺少 Python 包：pip install mlx-whisper", EXIT_VALIDATION) from exc

    audio = stage_extract_audio(video, work_dir)
    kwargs = {"path_or_hf_repo": model}
    if language:
        kwargs["language"] = language
    log(f"[transcribe] mlx-whisper model={model}")
    result = mlx_whisper.transcribe(str(audio), **kwargs)
    write_srt(result.get("segments", []), outputs["srt"])
    write_txt_from_srt(outputs["srt"], outputs["txt"])
    audio.unlink(missing_ok=True)
    return outputs, False


def run(args):
    kind, resolved = resolve_input(args.input)
    cookies = resolve_cookies(args.cookies, resolved)
    item_id = safe_id(resolved.stem) if kind == "file" else fetch_media_id(resolved, cookies)
    work_dir = Path(args.out).expanduser() / item_id
    plan = {
        "input": args.input,
        "input_kind": kind,
        "resolved": str(resolved),
        "id": item_id,
        "work_dir": str(work_dir),
        "cookies": str(cookies) if cookies else None,
        "height": args.height,
        "prefer": args.prefer,
        "merge_format": args.merge_format,
        "transcribe": args.transcribe,
        "model": args.model if args.transcribe else None,
        "language": args.language if args.transcribe else None,
        "summary": str(work_dir / "summary.txt") if args.transcribe else None,
    }
    if args.dry_run:
        return {"dry_run": True, "plan": plan}

    if kind == "file":
        video, cached = resolved, True
        work_dir.mkdir(parents=True, exist_ok=True)
        target = work_dir / f"video{resolved.suffix}"
        if not target.exists():
            shutil.copy2(resolved, target)
        video = target
    else:
        check_download_dependencies()
        video, cached = stage_download(resolved, work_dir, cookies, args.height, args.prefer, args.merge_format)

    data = {"video": str(video), "cached": cached, "plan": plan}
    if args.transcribe:
        transcripts, transcript_cached = stage_transcribe(video, work_dir, args.model, args.language)
        data["transcripts"] = {name: str(path) for name, path in transcripts.items()}
        data["summary"] = str(work_dir / "summary.txt")
        data["transcript_cached"] = transcript_cached
    return data


def schema():
    return {
        "ok": "boolean",
        "data": {
            "video": "string path",
            "cached": "boolean",
            "transcripts": "object, default unless --no-transcribe",
            "summary": "summary.txt path, generated by Agent",
            "dry_run": "boolean",
            "plan": "object",
        },
        "error": {"code": "string", "message": "string", "retryable": "boolean"},
        "exit_codes": {"0": "ok", "1": "runtime", "2": "auth", "3": "validation"},
    }


def format_file_size(path):
    size = path.stat().st_size
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / 1024 / 1024:.1f}MB"


def is_section_title(line, index):
    if index == 0 or CIRCLE_NUMBER_RE.search(line):
        return False
    return "：" in line and not line.lstrip().startswith(("│", "├", "└"))


def render_tree_content(text):
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return '<div class="empty-state">暂无摘要</div>'

    rendered = []
    for index, line in enumerate(lines):
        classes = []
        if index == 0:
            classes.append("tree-title")
        if is_section_title(line, index):
            classes.append("section-title")
        index_match = CIRCLE_NUMBER_RE.search(line)
        if index_match:
            prefix = escape(line[:index_match.start()], quote=False)
            indexed = escape(line[index_match.start():], quote=False)
            escaped = f'{prefix}<span class="has-index">{indexed}</span>'
        else:
            escaped = escape(line, quote=False)
        if classes:
            rendered.append(f'<span class="{" ".join(classes)}">{escaped}</span>')
        else:
            rendered.append(escaped)
    return "\n".join(rendered)


def render_transcript_content(text):
    lines = [
        re.sub(r"\s+", " ", raw_line).strip()
        for raw_line in text.splitlines()
        if raw_line.strip()
    ]
    if not lines:
        return '<div class="empty-state">暂无全文</div>'
    return escape("\n".join(lines), quote=False)


def build_viewer(work_dir):
    work_dir = Path(work_dir).expanduser()
    summary_path = work_dir / "summary.txt"
    transcript_path = work_dir / "transcript.txt"

    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else None
    transcript_text = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else None

    if summary_text and summary_text.strip():
        first_line = summary_text.strip().splitlines()[0]
        title = first_line[:64] + ("..." if len(first_line) > 64 else "")
    else:
        title = work_dir.name

    tabs = []
    panels = []
    active_set = False
    if summary_text:
        tabs.append('<button id="tab-summary" class="tab active" onclick="switchTab(\'summary\')">摘要</button>')
        panels.append(f'<div id="panel-summary" class="panel active"><pre class="tree-view">{render_tree_content(summary_text)}</pre></div>')
        active_set = True
    if transcript_text:
        active_class = "active" if not active_set else ""
        tabs.append(f'<button id="tab-transcript" class="tab {active_class}" onclick="switchTab(\'transcript\')">全文</button>')
        panels.append(f'<div id="panel-transcript" class="panel {active_class}"><pre class="transcript">{render_transcript_content(transcript_text)}</pre></div>')

    if not panels:
        panels.append('<div class="empty-state">未找到 summary.txt 或 transcript.txt</div>')

    meta_parts = []
    if summary_path.exists():
        meta_parts.append(f"摘要 {format_file_size(summary_path)}")
    if transcript_path.exists():
        meta_parts.append(f"全文 {format_file_size(transcript_path)}")
    meta = " · ".join(meta_parts) if meta_parts else str(work_dir)

    return HTML_TEMPLATE.format(
        title=escape(title, quote=False),
        meta=escape(meta, quote=False),
        tabs="\n".join(tabs),
        panels="\n".join(panels),
    )


def generate_viewer(work_dir):
    work_dir = Path(work_dir).expanduser()
    if not work_dir.exists():
        raise CliError("validation_error", f"目录不存在：{work_dir}", EXIT_VALIDATION)
    html_path = work_dir / "viewer.html"
    html_path.write_text(build_viewer(work_dir), encoding="utf-8")
    if sys.platform == "darwin":
        subprocess.run(["open", str(html_path)], check=False)
    else:
        webbrowser.open(html_path.resolve().as_uri())
    print(f"viewer: {html_path}")


def output_success(data, fmt, started_at):
    envelope = {
        "ok": True,
        "data": data,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "fetch-what-say",
            "elapsed_ms": int((time.time() - started_at) * 1000),
        },
    }
    if fmt == "json":
        print(json.dumps(envelope, ensure_ascii=False))
        return
    if data.get("dry_run"):
        plan = data["plan"]
        print(f"dry-run: {plan['resolved']}")
        print(f"work_dir: {plan['work_dir']}")
        return
    print(f"video: {data['video']}")
    if data.get("transcripts"):
        for name, path in data["transcripts"].items():
            print(f"{name}: {path}")
        print(f"summary: {data['summary']}")


def output_error(error, fmt, started_at):
    envelope = {
        "ok": False,
        "error": {"code": error.code, "message": error.message, "retryable": error.retryable},
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "tool": "fetch-what-say",
            "elapsed_ms": int((time.time() - started_at) * 1000),
        },
    }
    if fmt == "json":
        print(json.dumps(envelope, ensure_ascii=False))
        return
    print(f"error: {error.message}")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="yt-dlp 支持的 URL、BV、ep，或本地视频文件")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="输出根目录")
    parser.add_argument("--view", metavar="WORK_DIR", help="生成 viewer.html 并打开浏览器")
    parser.add_argument("--cookies", help="Netscape cookies.txt；不传时自动使用默认 cookies 目录")
    parser.add_argument("--height", type=int, default=360, help="最高分辨率")
    parser.add_argument("--prefer", choices=["size", "bitrate"], default="size", help="小体积或高码率")
    parser.add_argument("--merge-format", default="mp4", help="合并容器格式")
    parser.add_argument("--transcribe", dest="transcribe", action="store_true", default=True, help="输出 transcript.srt 和 transcript.txt，默认开启")
    parser.add_argument("--no-transcribe", dest="transcribe", action="store_false", help="只下载媒体，不转写")
    parser.add_argument("--model", default=DEFAULT_WHISPER_MODEL, help="mlx-whisper 模型")
    parser.add_argument("--language", default="zh", help="转写语言，如 zh、en、ja")
    parser.add_argument("--dry-run", action="store_true", help="只输出计划")
    parser.add_argument("--schema", action="store_true", help="输出 JSON 契约")
    parser.add_argument("--format", choices=["json", "table"], help="输出格式")
    return parser


def main():
    started_at = time.time()
    parser = build_parser()
    args = parser.parse_args()
    fmt = args.format or ("table" if sys.stdout.isatty() else "json")
    if args.schema:
        print(json.dumps(schema(), ensure_ascii=False, indent=2))
        return EXIT_OK
    try:
        if args.view:
            generate_viewer(args.view)
            return EXIT_OK
        if not args.input:
            raise CliError("validation_error", "缺少 input", EXIT_VALIDATION)
        output_success(run(args), fmt, started_at)
        return EXIT_OK
    except CliError as error:
        output_error(error, fmt, started_at)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
