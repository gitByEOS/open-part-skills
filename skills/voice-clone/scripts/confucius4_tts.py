#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


BASE_URL = "https://confucius4-tts.youdao.com/gradio"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_REFERENCE = SKILL_DIR / "assets" / "miss-arrogant.mp3"


def log(message: str) -> None:
    print(message, file=sys.stderr)


def request_bytes(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 600,
) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"请求失败: {error}") from error


def post_json(base_url: str, api_name: str, payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response = request_bytes(
        f"{base_url}/call/{api_name}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    data = json.loads(response.decode("utf-8"))
    event_id = data.get("event_id")
    if not event_id:
        raise SystemExit(f"接口未返回 event_id: {data!r}")
    return event_id


def fetch_sse_result(base_url: str, api_name: str, event_id: str) -> object:
    response = request_bytes(f"{base_url}/call/{api_name}/{event_id}")
    last_event = None
    last_data = None

    for raw_line in response.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("event:"):
            last_event = line[6:].strip()
        elif line.startswith("data:"):
            value = line[5:].strip()
            if value and value != "[DONE]":
                last_data = value

    if last_data is None:
        raise SystemExit("SSE 响应里没有 data")
    if last_event == "error":
        raise SystemExit(f"Gradio 任务失败: {last_data}")
    return json.loads(last_data)


def upload_reference_audio(base_url: str, reference_audio: Path) -> dict:
    boundary = f"----voice-clone-{uuid4().hex}"
    filename = reference_audio.name.encode("ascii", errors="ignore").decode("ascii")
    filename = filename or "reference_audio"
    mime_type = mimetypes.guess_type(reference_audio.name)[0] or "audio/mpeg"
    file_bytes = reference_audio.read_bytes()

    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                'Content-Disposition: form-data; name="files"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            file_bytes,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    response = request_bytes(
        f"{base_url}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    uploaded = json.loads(response.decode("utf-8"))
    if isinstance(uploaded, list):
        uploaded_file = uploaded[0]
    elif isinstance(uploaded, dict) and "files" in uploaded:
        uploaded_file = uploaded["files"][0]
    else:
        uploaded_file = uploaded

    if isinstance(uploaded_file, str):
        audio = {"path": uploaded_file}
    else:
        audio = dict(uploaded_file)

    audio.setdefault("url", None)
    audio.setdefault("orig_name", reference_audio.name)
    audio.setdefault("mime_type", mime_type)
    audio.setdefault("is_stream", False)
    audio.setdefault("meta", {"_type": "gradio.FileData"})
    return audio


def read_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    return Path(args.text_file).read_text(encoding="utf-8")


def reference_status(reference_data: object) -> str:
    if isinstance(reference_data, list) and len(reference_data) > 1:
        return str(reference_data[1])
    return str(reference_data)


def reference_state(reference_data: object) -> object:
    if isinstance(reference_data, list) and reference_data:
        return reference_data[0]
    return None


def download_url(base_url: str, predict_data: object) -> str:
    if not isinstance(predict_data, list) or len(predict_data) < 2:
        raise SystemExit(f"预测结果格式异常: {predict_data!r}")

    audio, status = predict_data[0], predict_data[1]
    log(f"状态: {status}")

    if isinstance(audio, dict):
        path = audio.get("path")
        url = audio.get("url")
    elif isinstance(audio, str):
        path = audio
        url = None
    else:
        raise SystemExit(f"音频结果格式异常: {audio!r}")

    if path:
        return f"{base_url}/file={path}"
    if url:
        return url
    raise SystemExit(f"音频结果缺少 url/path: {audio!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用 Confucius4-TTS Gradio API 合成参考音色语音。"
    )
    parser.add_argument("--text", default="", help="要合成的文本")
    parser.add_argument("--text-file", default="", help="从文件读取文本")
    parser.add_argument(
        "--reference",
        default=str(DEFAULT_REFERENCE),
        help="参考音色，默认 assets/miss-arrogant.mp3",
    )
    parser.add_argument("--lang", default="zh", help="语言代码，默认 zh")
    parser.add_argument(
        "--out", default="voice-clone-output.wav", help="输出 wav 文件"
    )
    parser.add_argument("--base-url", default=BASE_URL, help="Gradio 服务地址")
    args = parser.parse_args()

    if not args.text and not args.text_file:
        parser.error("必须提供 --text 或 --text-file")
    if args.text_file and not Path(args.text_file).is_file():
        parser.error(f"文本文件不存在: {args.text_file}")
    if not Path(args.reference).is_file():
        parser.error(f"参考音频不存在: {args.reference}")
    return args


def main() -> int:
    args = parse_args()
    reference_audio = Path(args.reference)
    output = Path(args.out)

    with tempfile.TemporaryDirectory():
        log("上传参考音频...")
        audio = upload_reference_audio(args.base_url, reference_audio)

        log("校验参考音频...")
        reference_event_id = post_json(
            args.base_url, "_gradio_reference_uploaded", {"data": [audio]}
        )
        reference_data = fetch_sse_result(
            args.base_url, "_gradio_reference_uploaded", reference_event_id
        )
        log(reference_status(reference_data))

        log("提交合成任务...")
        predict_event_id = post_json(
            args.base_url,
            "_gradio_predict",
            {"data": [read_text(args), args.lang, audio, reference_state(reference_data)]},
        )
        predict_data = fetch_sse_result(args.base_url, "_gradio_predict", predict_event_id)

        log("下载合成音频...")
        output.write_bytes(request_bytes(download_url(args.base_url, predict_data)))
        log(f"完成: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
