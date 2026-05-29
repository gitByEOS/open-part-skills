#!/usr/bin/env python3
"""
分段配音工作流：split / gen / match / merge

用法:
  python3 {skill}/scripts/narrator_voice.py split <input.md> <work_dir>
  python3 {skill}/scripts/narrator_voice.py gen <work_dir> [--voice xiaoxiao|xiaoyi] [--rate 1.175]
  python3 {skill}/scripts/narrator_voice.py match <work_dir>
  python3 {skill}/scripts/narrator_voice.py merge <work_dir> [--open]
"""
from pathlib import Path
import asyncio
import base64
import difflib
import os
import re
import sys
import webbrowser

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import narrator_core  # noqa: E402

EDGE_TTS_VOICES = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "xiaoyi": "zh-CN-XiaoyiNeural",
}

EDGE_TTS_PITCH = {
    "xiaoxiao": "-6Hz",
    "xiaoyi": "-10Hz",
}

USAGE = """用法:
  python3 {skill}/scripts/narrator_voice.py split <input.md> <work_dir>
  python3 {skill}/scripts/narrator_voice.py gen <work_dir> [--voice xiaoxiao|xiaoyi] [--rate 1.175]
  python3 {skill}/scripts/narrator_voice.py match <work_dir>
  python3 {skill}/scripts/narrator_voice.py merge <work_dir> [--open]"""

def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else Path.cwd() / path

def parse_option(argv: list[str], name: str, default: str) -> str:
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        print(f"{name} 缺少参数")
        sys.exit(1)
    return argv[index + 1]

def load_srt_texts(srt_file: Path) -> list[str]:
    content = srt_file.read_text(encoding="utf-8")
    texts = []
    for part in re.split(r"## \[\d+\]", content)[1:]:
        text_lines = [
            line.strip()
            for line in part.strip().split("\n")
            if line.strip() and not line.startswith("⚪") and not line.startswith("（")
        ]
        texts.append(" ".join(text_lines) if text_lines else "")
    return texts

def _split_for_tts(text: str, max_len: int = 350) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        if end >= len(text):
            chunks.append(text[start:])
            break
        boundary = -1
        for ch in "\n。！？；.!?;":
            pos = text.rfind(ch, start, end)
            if pos > start:
                boundary = max(boundary, pos)
        if boundary > start:
            chunks.append(text[start : boundary + 1])
            start = boundary + 1
            continue
        for ch in "，, ":
            pos = text.rfind(ch, start, end)
            if pos > start:
                boundary = max(boundary, pos)
        if boundary > start:
            chunks.append(text[start : boundary + 1])
            start = boundary + 1
        else:
            chunks.append(text[start:end])
            start = end
    return chunks

def cmd_split(argv: list[str]) -> None:
    if len(argv) < 2:
        print("用法: python3 {skill}/scripts/narrator_voice.py split <input.md> <work_dir>")
        sys.exit(1)

    input_file = resolve_path(argv[0]).resolve()
    output_dir = resolve_path(argv[1]).resolve()

    if not input_file.is_file():
        print(f"文件不存在: {input_file}")
        sys.exit(1)

    narrator_core.BASE_DIR = os.environ.get("BLOG_NARRATOR_IMAGE_BASE", os.getcwd())

    md_text = input_file.read_text(encoding="utf-8")
    content_md = narrator_core.strip_horizontal_rules(narrator_core.strip_frontmatter(md_text))
    body_html = narrator_core.embed_images(narrator_core.md_to_html(content_md))
    texts = narrator_core.extract_slide_texts(body_html)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audio").mkdir(exist_ok=True)
    (output_dir / "src.md").write_text(md_text, encoding="utf-8")

    lines = [f"# 共 {len(texts)} 段\n\n"]
    for i, text in enumerate(texts, 1):
        if not re.search(r"[a-zA-Z一-鿿0-9]", text):
            lines.append(f"## [{i}] ⚪ （跳过空行）\n\n")
        else:
            lines.append(f"## [{i}]\n\n{text}\n\n")

    srt_file = output_dir / "srt.md"
    srt_file.write_text("".join(lines), encoding="utf-8")

    wd = output_dir
    print(f"已导出: {srt_file}")
    print(f"音频目录: {wd / 'audio'}")
    print(f"源文件: {wd / 'src.md'}")
    print("\n下一步:")
    print(f"  python3 {{skill}}/scripts/narrator_voice.py gen {wd}")
    print(f"  # 或手动放入 audio/ 后，非 N.mp3 命名时:")
    print(f"  python3 {{skill}}/scripts/narrator_voice.py match {wd}")
    print(f"  python3 {{skill}}/scripts/narrator_voice.py merge {wd} --open")

async def _generate_audio(texts: list[str], voice: str, rate: float, pitch: str, audio_dir: Path) -> None:
    import edge_tts

    for index, text in enumerate(texts, 1):
        if not re.search(r"[a-zA-Z一-鿿0-9]", text):
            print(f"  [{index}] ⚪ 跳过空行")
            continue

        audio_parts = []
        for chunk in _split_for_tts(text):
            try:
                comm = edge_tts.Communicate(
                    chunk, voice, rate=f"+{round((rate - 1) * 100)}%", pitch=pitch
                )
                part_chunks = []
                async for part in comm.stream():
                    if part["type"] == "audio":
                        part_chunks.append(part["data"])
                if part_chunks:
                    audio_parts.append(b"".join(part_chunks))
            except Exception as exc:
                print(f"  [{index}] ⚠️ 失败: {exc}")

        if audio_parts:
            combined = b"".join(audio_parts)
            audio_file = audio_dir / f"{index}.mp3"
            audio_file.write_bytes(combined)
            display = text[:40] + "..." if len(text) > 40 else text
            print(f"  [{index}] {audio_file.name} ({len(combined)} bytes) - {display}")
        else:
            print(f"  [{index}] ⚠️ 无音频")

def cmd_gen(argv: list[str]) -> None:
    if len(argv) < 1:
        print("用法: python3 {skill}/scripts/narrator_voice.py gen <work_dir> [--voice xiaoxiao|xiaoyi] [--rate 1.175]")
        sys.exit(1)

    work_dir = resolve_path(argv[0]).resolve()
    srt_file = work_dir / "srt.md"
    audio_dir = work_dir / "audio"

    if not srt_file.exists():
        print(f"分段文本不存在: {srt_file}")
        sys.exit(1)

    voice_name = parse_option(argv, "--voice", "xiaoxiao")
    if voice_name not in EDGE_TTS_VOICES:
        print(f"--voice 仅支持: {', '.join(EDGE_TTS_VOICES)}")
        sys.exit(1)

    try:
        rate = float(parse_option(argv, "--rate", "1.175"))
    except ValueError:
        print("--rate 需要指定数字")
        sys.exit(1)

    audio_dir.mkdir(parents=True, exist_ok=True)
    texts = load_srt_texts(srt_file)
    voice = EDGE_TTS_VOICES[voice_name]
    pitch = EDGE_TTS_PITCH[voice_name]

    print(f"分段: {len(texts)} 段")
    print(f"音色: {voice_name} ({voice})")
    print(f"速率: {rate}")
    print("=" * 60)

    asyncio.run(_generate_audio(texts, voice, rate, pitch, audio_dir))

    print("=" * 60)
    print(f"音频目录: {audio_dir}")
    print(f"\n下一步:\npython3 {{skill}}/scripts/narrator_voice.py merge {work_dir} --open")

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

def cmd_match(argv: list[str]) -> None:
    if len(argv) < 1:
        print("用法: python3 {skill}/scripts/narrator_voice.py match <work_dir>")
        sys.exit(1)

    import onnxruntime as ort

    work_dir = resolve_path(argv[0]).resolve()
    audio_dir = work_dir / "audio"
    srt_file = work_dir / "srt.md"

    if not audio_dir.is_dir():
        print(f"音频目录不存在: {audio_dir}")
        sys.exit(1)
    if not srt_file.exists():
        print(f"分段文本不存在: {srt_file}")
        sys.exit(1)

    texts = load_srt_texts(srt_file)
    audio_files = (
        sorted(audio_dir.glob("*.mp3"))
        + sorted(audio_dir.glob("*.wav"))
        + sorted(audio_dir.glob("*.m4a"))
    )
    if not audio_files:
        print("无音频文件")
        sys.exit(1)

    model_path = narrator_core.MODEL_DIR / "model.int8.onnx"
    tokens_path = narrator_core.MODEL_DIR / "tokens.json"
    cmvn_path = narrator_core.MODEL_DIR / "am.mvn"
    narrator_core.ensure_model_files(model_path, tokens_path, cmvn_path)

    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    meta = narrator_core.load_meta(session, cmvn_path)
    tokens = narrator_core.load_tokens(tokens_path)

    print(f"分段: {len(texts)} 段, 音频: {len(audio_files)} 个")
    print("=" * 60)

    matches: dict[Path, int] = {}
    for audio_file in audio_files:
        print(f"\n识别: {audio_file.name}")
        waveform = narrator_core.read_audio(audio_file)
        asr_text = narrator_core.transcribe(session, meta, tokens, waveform, "zh", True)
        print(f"  ASR: {asr_text[:60]}{'...' if len(asr_text) > 60 else ''}")

        idx, score = _match_text(asr_text, texts)
        if score < 0.3:
            print(f"  ⚠️ 置信度低 ({score:.2f})，跳过")
            continue

        matches[audio_file] = idx
        display = texts[idx - 1][:40] if texts[idx - 1] else "⚪"
        print(f"  → [{idx}] {display} (score={score:.2f})")

    print("\n" + "=" * 60)
    print("重命名:")
    for audio_file, idx in matches.items():
        ext = audio_file.suffix.lstrip(".")
        new_path = audio_dir / f"{idx}.{ext}"
        if new_path.exists() and new_path != audio_file:
            print(f"  ⚠️ {new_path.name} 已存在，跳过")
        else:
            audio_file.rename(new_path)
            print(f"  {audio_file.name} → {new_path.name}")

    print(f"\n下一步:\npython3 {{skill}}/scripts/narrator_voice.py merge {work_dir} --open")

def cmd_merge(argv: list[str]) -> None:
    if len(argv) < 1:
        print("用法: python3 {skill}/scripts/narrator_voice.py merge <work_dir> [--open]")
        sys.exit(1)

    work_dir = resolve_path(argv[0]).resolve()
    should_open = "--open" in argv

    if not work_dir.is_dir():
        print(f"目录不存在: {work_dir}")
        sys.exit(1)

    audio_dir = work_dir / "audio"
    input_file = work_dir / "src.md"
    if not audio_dir.is_dir():
        print(f"音频目录不存在: {audio_dir}")
        sys.exit(1)
    if not input_file.is_file():
        print(f"未找到源文件: {input_file}")
        sys.exit(1)

    narrator_core.BASE_DIR = os.environ.get("BLOG_NARRATOR_IMAGE_BASE", os.getcwd())

    md_text = input_file.read_text(encoding="utf-8")
    content_md = narrator_core.strip_horizontal_rules(narrator_core.strip_frontmatter(md_text))
    title = narrator_core.extract_title(content_md, input_file.name)
    body_html = narrator_core.embed_images(narrator_core.md_to_html(content_md))
    texts = narrator_core.extract_slide_texts(body_html)

    srt_file = work_dir / "srt.md"
    if srt_file.exists():
        match = re.search(r"# 共 (\d+) 段", srt_file.read_text(encoding="utf-8"))
        segment_count = int(match.group(1)) if match else len(texts)
    else:
        segment_count = len(texts)

    audio_sources = []
    for i in range(1, segment_count + 1):
        audio_file = None
        for ext in ("mp3", "wav", "m4a", "ogg"):
            candidate = audio_dir / f"{i}.{ext}"
            if candidate.exists():
                audio_file = candidate
                break

        if audio_file:
            mime = "audio/mp4" if audio_file.suffix == ".m4a" else f"audio/{audio_file.suffix[1:]}"
            data = base64.b64encode(audio_file.read_bytes()).decode("ascii")
            audio_sources.append(f"data:{mime};base64,{data}")
            print(f"  [{i}] {audio_file.name}")
        else:
            audio_sources.append(None)
            print(f"  [{i}] ⚠️ 缺失")

    output_file = work_dir / f"{input_file.stem}_voice.html"
    output_file.write_text(narrator_core.build_stage_html(title, body_html, audio_sources, 1.0), encoding="utf-8")

    print(f"\n已导出: {output_file} ({output_file.stat().st_size} bytes)")
    if should_open:
        webbrowser.open(output_file.resolve().as_uri())

COMMANDS = {
    "split": cmd_split,
    "gen": cmd_gen,
    "match": cmd_match,
    "merge": cmd_merge,
}

def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0 if len(sys.argv) > 1 else 1)

    command = sys.argv[1]
    handler = COMMANDS.get(command)
    if not handler:
        print(f"未知子命令: {command}\n")
        print(USAGE)
        sys.exit(1)

    handler(sys.argv[2:])

if __name__ == "__main__":
    main()
