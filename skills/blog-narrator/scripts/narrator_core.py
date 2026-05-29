#!/usr/bin/env python3
"""
blog-narrator 核心：Markdown 转 HTML、图片嵌入、逐行披露 stage、ASR 匹配。
"""
import os
import re
import base64
import json
import urllib.request
import subprocess
from pathlib import Path
from html.parser import HTMLParser

BASE_DIR = os.getcwd()

def md_to_html(md_text: str) -> str:
    """极简 Markdown 转 HTML，保留常见语法。"""
    lines = md_text.split("\n")
    out = []
    in_code_block = False
    in_list = False
    in_table = False
    table_has_header = False

    for line in lines:
        stripped = line.strip()

        # --- fenced code block ---
        if stripped.startswith("```"):
            if in_code_block:
                out.append("</code></pre>")
                in_code_block = False
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if in_table:
                    out.append("</tbody></table>")
                    in_table = False
                    table_has_header = False
                lang = stripped[3:].strip()
                out.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue

        if in_code_block:
            out.append(_escape_html(line))
            continue

        # --- table ---
        if re.match(r"^\|.*\|$", stripped) or re.match(r"^\|-+", stripped):
            if in_list:
                out.append("</ul>")
                in_list = False
            if not in_table:
                in_table = True
                table_has_header = False
                out.append("<table>")
            if re.match(r"^\|?[\s:-]+\|", stripped) and "=" not in stripped and "---" in stripped:
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if any("---" in c for c in cells):
                continue
            if not table_has_header:
                cells_html = "".join(f"<th>{_inline(c)}</th>" for c in cells)
                out.append(f"<thead><tr>{cells_html}</tr></thead><tbody>")
                table_has_header = True
            else:
                cells_html = "".join(f"<td>{_inline(c)}</td>" for c in cells)
                out.append(f"<tr>{cells_html}</tr>")
            continue
        elif in_table:
            out.append("</tbody></table>")
            in_table = False
            table_has_header = False

        # --- headings ---
        m = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        # --- empty line ---
        if stripped == "":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue

        # --- unordered list ---
        if stripped.startswith("- "):
            if not in_list:
                in_list = True
                out.append("<ul>")
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        elif in_list:
            out.append("</ul>")
            in_list = False

        # --- paragraph (supports <br> for trailing spaces) ---
        has_br = line.endswith("    ") or line.endswith("  ")
        p_content = _inline(stripped)
        if has_br:
            p_content += "<br>"
        out.append(f"<p>{p_content}</p>")

    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</tbody></table>")

    return "\n".join(out)

def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _inline(s: str) -> str:
    s = _escape_html(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
    s = re.sub(r"`([^`]+)`", r'<code>\1</code>', s)
    return s

def embed_images(body_html: str) -> str:
    """将 /pics/xxx.png 形式的图片转为 base64 内嵌。"""

    def _replace(m: re.Match) -> str:
        alt = m.group(1) or ""
        rel_path = m.group(2)  # e.g. /pics/xxx.png
        # 去掉前导 / 使其相对于 BASE_DIR
        img_path = os.path.join(BASE_DIR, rel_path.lstrip("/"))
        if not os.path.isfile(img_path):
            return m.group(0)  # 找不到则原样保留
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{img_b64}" alt="{alt}">'

    return re.sub(r"!\[(.*?)\]\((/pics/[^)]+)\)", _replace, body_html)

# ====== 逐行披露 stage ======

def strip_frontmatter(md_text: str) -> str:
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return md_text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :]).lstrip("\n")
    return md_text

def strip_horizontal_rules(md_text: str) -> str:
    lines = [line for line in md_text.splitlines() if not re.match(r"^\s*-{3,}\s*$", line)]
    return "\n".join(lines)

def extract_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback

# ====== 语音相关 ======

VOICE_CSS = """
#voice-panel {
  position: fixed;
  left: 18px;
  bottom: 14px;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 8px;
}
#voice-control {
  border: 1px solid rgba(122, 47, 36, 0.2);
  border-radius: 999px;
  padding: 7px 12px;
  color: rgba(89, 68, 50, 0.68);
  background: rgba(255, 250, 240, 0.76);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  backdrop-filter: blur(8px);
}
#voice-control:hover {
  color: #7a2f24;
  border-color: rgba(122, 47, 36, 0.36);
}
#voice-status {
  border: 1px solid rgba(122, 47, 36, 0.14);
  border-radius: 999px;
  padding: 7px 10px;
  color: rgba(89, 68, 50, 0.68);
  background: rgba(255, 250, 240, 0.58);
  font-size: 13px;
  user-select: none;
  backdrop-filter: blur(8px);
}
"""

VOICE_SCRIPT = """
  var voiceButton = document.getElementById('voice-control');
  var voiceStatus = document.getElementById('voice-status');
  var audioSources = __AUDIO_SOURCES__;
  var currentAudio = null;
  var isVoiceEnabled = true;
  var voiceRate = __VOICE_RATE__;
  var synth = audioSources ? null : (window.speechSynthesis || null);
  var selectedVoice = null;

  function loadVoice() {
    if (!synth) return;
    var voices = synth.getVoices();
    selectedVoice = voices.find(function(voice){
      return voice.lang && voice.lang.toLowerCase().indexOf('zh') === 0;
    }) || voices[0] || null;
  }

  function readableText(line) {
    if (!line) return '';
    var text = line.innerText || line.textContent || '';
    return text.replace(/\\s+/g, ' ').trim();
  }

  function setVoiceStatus(text) {
    voiceStatus.textContent = text;
  }

  function playAudioLine(index) {
    if (!audioSources || !isVoiceEnabled || !audioSources[index]) return false;
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }
    currentAudio = new Audio(audioSources[index]);
    currentAudio.onended = function(){
      if (isVoiceEnabled) setVoiceStatus('待播放');
    };
    setVoiceStatus('播放中');
    currentAudio.play();
    return true;
  }

  function speakLine(index, line) {
    if (playAudioLine(index)) return;
    if (!synth || !isVoiceEnabled) return;
    var text = readableText(line);
    if (!text) return;
    synth.cancel();
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN';
    utterance.rate = voiceRate;
    utterance.pitch = 1;
    if (selectedVoice) utterance.voice = selectedVoice;
    utterance.onstart = function(){ setVoiceStatus('播放中'); };
    utterance.onend = function(){
      if (isVoiceEnabled) setVoiceStatus('待播放');
    };
    synth.speak(utterance);
  }

  function syncVoiceButton() {
    if (!synth) {
      voiceButton.textContent = '朗读当前行';
      setVoiceStatus(audioSources ? (isVoiceEnabled ? '待播放' : '× 静音') : '声音不可用');
      voiceButton.disabled = !audioSources;
      return;
    }
    voiceButton.textContent = '朗读当前行';
    setVoiceStatus(isVoiceEnabled ? '待播放' : '× 静音');
  }

  function toggleVoice() {
    if (!synth && !audioSources) return;
    isVoiceEnabled = !isVoiceEnabled;
    if (!isVoiceEnabled && synth) synth.cancel();
    if (!isVoiceEnabled && currentAudio) currentAudio.pause();
    syncVoiceButton();
  }

  voiceButton.addEventListener('click', function(){
    if (!synth && !audioSources) return;
    isVoiceEnabled = true;
    syncVoiceButton();
    speakLine(visibleCount - 1, lines[visibleCount - 1]);
  });
  loadVoice();
  syncVoiceButton();
  if (synth) synth.onvoiceschanged = loadVoice;
"""

_VOID = {"br", "hr", "img", "input", "meta", "link", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
_NON_SPEAKABLE = {"img", "hr"}

class SlideTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.depth = 0
        self.current = []
        self.capture = False
        self.capture_tag = None
        self.in_ul = False

    def handle_starttag(self, tag, attrs):
        if tag not in _VOID:
            self.depth += 1
        if self.depth == 1:
            if tag in {"ul", "ol"}:
                self.in_ul = True
            elif not self.capture and tag in _NON_SPEAKABLE:
                self.lines.append("")
            elif not self.capture and tag in {"h1", "h2", "h3", "h4", "p", "blockquote", "pre", "table", "strong", "code", "li"}:
                self.capture = True
                self.capture_tag = tag
                self.current = []
        elif self.in_ul and self.depth == 2 and tag == "li" and not self.capture:
            self.capture = True
            self.capture_tag = "li"
            self.current = []

    def handle_data(self, data):
        if self.capture:
            self.current.append(data)

    def handle_endtag(self, tag):
        if self.capture and tag == self.capture_tag:
            text = re.sub(r"\s+", " ", "".join(self.current)).strip()
            self.lines.append(text)
            self.capture = False
            self.current = []
        if tag in {"ul", "ol"}:
            self.in_ul = False
        if tag not in _VOID:
            self.depth -= 1

def extract_slide_texts(body_html: str) -> list[str]:
    parser = SlideTextParser()
    parser.feed(body_html)
    return parser.lines

# ====== HTML 构建 ======

def build_stage_html(title: str, body_html: str, audio_sources: list[str] | None = None, rate: float = 1.0) -> str:
    voice_enabled = audio_sources is not None or rate != 1.0
    voice_panel = (
        '<div id="voice-panel">'
        '<button id="voice-control" type="button">朗读当前行</button>'
        '<span id="voice-status">待播放</span>'
        '</div>\n'
        if voice_enabled else ""
    )
    voice_style = VOICE_CSS if voice_enabled else ""

    audio_json = json.dumps(audio_sources, ensure_ascii=False) if audio_sources else "null"
    voice_js = VOICE_SCRIPT.replace("__AUDIO_SOURCES__", audio_json).replace("__VOICE_RATE__", str(rate)) if voice_enabled else ""

    # 语音版额外 JS 插入
    speak_after_render = "\n    speakLine(visibleCount - 1, lines[visibleCount - 1]);" if voice_enabled else ""
    speak_after_init = "\n  speakLine(visibleCount - 1, lines[visibleCount - 1]);" if voice_enabled else ""
    cancel_on_close = "\n      if (synth) synth.cancel();" if voice_enabled else ""
    voice_keys = (
        "    if (e.key === 'Shift') {\n"
        "      e.preventDefault();\n"
        "      toggleVoice();\n"
        "    }\n"
        "    if (e.key === 'Control' || e.key === 'Enter') {\n"
        "      e.preventDefault();\n"
        "      isVoiceEnabled = true;\n"
        "      syncVoiceButton();\n"
        "      speakLine(visibleCount - 1, lines[visibleCount - 1]);\n"
        "    }\n" if voice_enabled else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - Blog Stage</title>
<style>
{voice_style}
*, *::before, *::after {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  min-height: 100vh;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, 'Helvetica Neue', Arial, sans-serif;
  color: #213547;
  background:
    radial-gradient(circle at 18% 12%, rgba(160, 56, 48, 0.08), transparent 28%),
    linear-gradient(135deg, #fffaf0 0%, #f8f3e7 44%, #f7fbf6 100%);
  line-height: 1.72;
  font-size: 24px;
  -webkit-font-smoothing: antialiased;
}}
body::before {{
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.42) 48%, transparent 100%),
    repeating-linear-gradient(90deg, rgba(76, 55, 35, 0.025) 0 1px, transparent 1px 9px);
  mix-blend-mode: multiply;
}}
body::after {{
  content: "";
  position: fixed;
  left: -60px;
  top: -64px;
  width: 260px;
  height: 304px;
  pointer-events: none;
  background:
    radial-gradient(ellipse 24px 50px at 54% 18%, rgba(83, 145, 132, 0.24), rgba(83, 145, 132, 0.10) 42%, transparent 68%),
    radial-gradient(ellipse 22px 58px at 69% 30%, rgba(83, 145, 132, 0.20), rgba(83, 145, 132, 0.08) 43%, transparent 68%),
    radial-gradient(ellipse 28px 70px at 43% 43%, rgba(83, 145, 132, 0.22), rgba(83, 145, 132, 0.09) 32%, transparent 60%),
    radial-gradient(ellipse 20px 51px at 61% 56%, rgba(83, 145, 132, 0.18), rgba(83, 145, 132, 0.07) 43%, transparent 68%),
    radial-gradient(ellipse 18px 46px at 24% 62%, rgba(83, 145, 132, 0.145), rgba(83, 145, 132, 0.052) 42%, transparent 68%),
    radial-gradient(ellipse 21px 54px at 7% 74%, rgba(83, 145, 132, 0.15), rgba(83, 145, 132, 0.055) 43%, transparent 68%),
    radial-gradient(ellipse 19px 50px at 17% 86%, rgba(83, 145, 132, 0.16), rgba(83, 145, 132, 0.06) 42%, transparent 68%),
    radial-gradient(ellipse 17px 45px at 30% 80%, rgba(83, 145, 132, 0.14), rgba(83, 145, 132, 0.05) 42%, transparent 68%),
    linear-gradient(138deg, transparent 47%, rgba(83, 145, 132, 0.045) 49% 51%, transparent 53%);
  opacity: 0.82;
  transform: rotate(-24deg);
  transform-origin: 18% 12%;
  animation: leafBreeze 4.8s ease-in-out infinite alternate;
}}
body.title-only {{
  display: grid;
  place-items: center;
  overflow: hidden;
}}
#stage {{
  width: min(920px, calc(100vw - 64px));
  min-height: 100vh;
  margin: 0 auto;
  padding: 72px 0 96px;
}}
body.title-only #stage {{
  min-height: auto;
  padding: 0;
  text-align: center;
}}
.reveal-line {{
  display: none;
  opacity: 0;
  transform: translate3d(0, 9px, 0);
}}
.reveal-line.visible {{
  display: revert;
  opacity: 1;
  transform: translateY(0);
  animation: inkReveal 350ms linear both;
  backface-visibility: hidden;
  will-change: opacity, transform, filter;
}}
.reveal-list:not(.list-visible) {{
  display: none;
}}
h1 {{
  font-family: "Songti SC", "STSong", "Noto Serif CJK SC", serif;
  font-size: clamp(2.8rem, 8vw, 6rem);
  font-weight: 700;
  margin: 0 0 28px;
  letter-spacing: -0.04em;
  line-height: 1.08;
  color: #2d261f;
  text-shadow: 0 16px 42px rgba(88, 63, 40, 0.14);
}}
h2 {{
  font-family: "Songti SC", "STSong", "Noto Serif CJK SC", serif;
  font-size: 2.2rem;
  font-weight: 650;
  margin: 64px 0 20px;
  padding-bottom: 12px;
  border-bottom: none;
  color: #7a2f24;
}}
h2::after {{
  content: "";
  display: block;
  width: min(360px, 58%);
  height: 2px;
  margin-top: 5px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(36, 67, 58, 0.62), rgba(159, 70, 54, 0.28), transparent);
}}
h3 {{ font-size: 1.65rem; font-weight: 650; margin: 42px 0 14px; }}
h4 {{ font-size: 1.35rem; font-weight: 650; margin: 32px 0 10px; }}
p {{ margin: 0 0 22px; }}
ul, ol {{ padding-left: 32px; margin: 0 0 22px; }}
li {{ margin-bottom: 8px; }}
a {{ color: #3eaf7c; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{
  font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.875em;
  background: #f1f1f2;
  padding: 2px 7px;
  border-radius: 5px;
  color: #3e63dd;
}}
pre {{
  background: #f6f6f7;
  border: 1px solid #e2e2e3;
  border-radius: 10px;
  padding: 20px 24px;
  overflow-x: auto;
  margin: 0 0 24px;
  font-size: 0.78em;
  line-height: 1.65;
}}
pre code {{
  background: none;
  padding: 0;
  border-radius: 0;
  color: #3c3c43;
  font-size: inherit;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 28px;
  font-size: 0.86em;
}}
th, td {{
  border: 1px solid #e2e2e3;
  padding: 10px 16px;
  text-align: left;
}}
th {{ background: #f6f6f7; font-weight: 650; }}
blockquote {{
  border-left: 5px solid #9f4636;
  margin: 0 0 24px;
  padding: 10px 20px;
  background: rgba(255, 250, 240, 0.72);
  border-radius: 0 6px 6px 0;
  color: #5a5a5a;
}}
strong {{ font-weight: 650; color: #213547; }}
hr {{ border: none; border-top: 1px solid #e2e2e3; margin: 42px 0; }}
img {{ max-width: 100%; height: auto; margin: 20px 0; border-radius: 10px; border: 1px solid #e2e2e3; cursor: zoom-in; transition: opacity 0.2s; }}
img:hover {{ opacity: 0.85; }}
#lightbox {{ display: none; position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.85); justify-content: center; align-items: center; cursor: zoom-out; }}
#lightbox.active {{ display: flex; }}
#lightbox img {{ max-width: 90vw; max-height: 90vh; margin: 0; border: none; border-radius: 4px; box-shadow: 0 4px 40px rgba(0,0,0,0.5); }}
#hint {{
  position: fixed;
  right: 18px;
  bottom: 14px;
  color: rgba(89, 68, 50, 0.56);
  font-size: 13px;
  user-select: none;
}}
#start-tip {{
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, 60px);
  color: rgba(89, 68, 50, 0.56);
  font-size: 16px;
  opacity: 0;
  transition: opacity 0.15s;
}}
body.title-only #start-tip {{
  opacity: 1;
}}
@keyframes inkReveal {{
  0% {{ opacity: 0; filter: blur(9px); transform: translate3d(0, 11.25px, 0); }}
  100% {{ opacity: 1; filter: blur(0.18px); transform: translate3d(0, 0, 0); }}
}}
@keyframes leafBreeze {{
  0% {{ transform: rotate(-18deg) translate3d(0, 0, 0); opacity: 0.72; }}
  100% {{ transform: rotate(-20deg) translate3d(5px, -2px, 0); opacity: 0.76; }}
}}
</style>
</head>
<body class="title-only">
<div id="start-tip">按 [空格] 逐行朗读</div>
{voice_panel}
<main id="stage">
{body_html}
</main>
<div id="hint">←/↑ 上一行　↓/→ 下一行　Ctrl/Enter 重读　Shift 静音</div>
<div id="lightbox"><img id="lightbox-img" src=""></div>
<script>
(function(){{
  var stage = document.getElementById('stage');
  var lines = collectLines();
  var visibleCount = lines.length ? 1 : 0;

  lines.forEach(function(line){{
    line.classList.add('reveal-line');
  }});

  function collectLines() {{
    return Array.prototype.reduce.call(stage.children, function(result, child){{
      if ((child.tagName === 'UL' || child.tagName === 'OL') && child.children.length) {{
        child.classList.add('reveal-list');
        return result.concat(Array.prototype.slice.call(child.children));
      }}
      result.push(child);
      return result;
    }}, []);
  }}

  function render(shouldScroll) {{
    var sectionStart = getActiveSectionStart();
    lines.forEach(function(line, index){{
      line.classList.toggle('visible', isLineVisible(index, sectionStart));
    }});
    document.querySelectorAll('.reveal-list').forEach(function(list){{
      list.classList.toggle('list-visible', !!list.querySelector('.visible'));
    }});
    document.body.classList.toggle('title-only', visibleCount <= 1);
    if (shouldScroll && visibleCount > 1) {{
      requestAnimationFrame(function(){{
        window.scrollTo({{ top: document.documentElement.scrollHeight, behavior: 'smooth' }});
      }});
    }}{speak_after_render}
  }}

  function getActiveSectionStart() {{
    for (var index = visibleCount - 1; index > 0; index--) {{
      if (lines[index].tagName === 'H2') return index;
    }}
    return 0;
  }}

  function isLineVisible(index, sectionStart) {{
    if (index >= visibleCount) return false;
    if (sectionStart === 0) return true;
    return index === 0 || index >= sectionStart;
  }}

  function step(delta) {{
    var nextCount = Math.max(1, Math.min(lines.length, visibleCount + delta));
    if (nextCount === visibleCount) return;
    visibleCount = nextCount;
    render(delta > 0);
  }}

  document.addEventListener('keydown', function(e){{
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {{
      e.preventDefault();
      step(1);
    }}
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {{
      e.preventDefault();
      step(-1);
    }}
    if (e.key === 'Escape') {{
      document.getElementById('lightbox').classList.remove('active');{cancel_on_close}
    }}
{voice_keys}  }});

{voice_js}
  var lb = document.getElementById('lightbox');
  var lbImg = document.getElementById('lightbox-img');
  document.querySelectorAll('img').forEach(function(img){{
    img.addEventListener('click', function(){{
      if (!img.src || img.id === 'lightbox-img') return;
      lbImg.src = img.src;
      lb.classList.add('active');
    }});
  }});
  lb.addEventListener('click', function(){{
    lb.classList.remove('active');
  }});

  render(false);{speak_after_init}
}})();
</script>
</body>
</html>"""

# ====== ASR（SenseVoice，供 narrator_voice match） ======

SAMPLE_RATE = 16000
PREEMPH = 0.97
SCRIPTS_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPTS_DIR / "models"
MODEL_URL = "https://modelscope.cn/models/iic/SenseVoiceSmall-onnx/resolve/master/model_quant.onnx"
TOKENS_URL = "https://modelscope.cn/models/iic/SenseVoiceSmall-onnx/resolve/master/tokens.json"
CMVN_URL = "https://modelscope.cn/models/iic/SenseVoiceSmall-onnx/resolve/master/am.mvn"

def _load_numpy():
    import numpy as np

    return np

def load_tokens(path):
    path = Path(path)
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            return {index: token for index, token in enumerate(json.load(f))}

    table = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                table[int(parts[1])] = parts[0]
    return table

def download_file(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[download] {path.name}")
    with urllib.request.urlopen(url) as response, open(path, "wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)

def ensure_model_files(model_path, tokens_path, cmvn_path):
    model_path = Path(model_path)
    tokens_path = Path(tokens_path)
    cmvn_path = Path(cmvn_path)

    if not model_path.exists():
        download_file(MODEL_URL, model_path)

    if not tokens_path.exists():
        download_file(TOKENS_URL, tokens_path)

    if not cmvn_path.exists():
        download_file(CMVN_URL, cmvn_path)

def read_kaldi_vector(text, name):
    np = _load_numpy()
    match = re.search(rf"<{name}>.*?\[\s*(.*?)\s*\]", text, re.S)
    if not match:
        raise ValueError(f"am.mvn 缺少 {name}")
    return np.array([float(item) for item in match.group(1).split()], dtype=np.float32)

def load_cmvn(path):
    text = Path(path).read_text(encoding="utf-8")
    return read_kaldi_vector(text, "AddShift"), read_kaldi_vector(text, "Rescale")

def load_meta(session, cmvn_path):
    np = _load_numpy()
    custom = session.get_modelmeta().custom_metadata_map

    def to_int(key, default=0):
        value = custom.get(key)
        if value is None:
            return default
        number = float(value)
        return int(number) if number == int(number) else number

    if "neg_mean" in custom and "inv_stddev" in custom:
        neg_mean = np.array([float(x) for x in custom["neg_mean"].split(",")], dtype=np.float32)
        inv_std = np.array([float(x) for x in custom["inv_stddev"].split(",")], dtype=np.float32)
    else:
        neg_mean, inv_std = load_cmvn(cmvn_path)

    return {
        "window_size": to_int("lfr_window_size", 7),
        "window_shift": to_int("lfr_window_shift", 6),
        "normalize_samples": to_int("normalize_samples", 0) != 0,
        "blank_id": to_int("blank_id", 0),
        "with_itn_id": to_int("with_itn", 14),
        "without_itn_id": to_int("without_itn", 15),
        "lang": {
            "auto": to_int("lang_auto", 0),
            "zh": to_int("lang_zh", 3),
            "en": to_int("lang_en", 4),
            "ja": to_int("lang_ja", 11),
            "ko": to_int("lang_ko", 12),
            "yue": to_int("lang_yue", 7),
        },
        "neg_mean": neg_mean,
        "inv_std": inv_std,
    }

def read_audio(path):
    np = _load_numpy()
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-f",
        "f32le",
        "pipe:1",
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"音频解码失败，请确认已安装 ffmpeg: {message}")

    return np.frombuffer(result.stdout, dtype=np.float32).copy()

def hamming(length):
    np = _load_numpy()
    return 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(length) / (length - 1))

def hz_to_mel(hz):
    np = _load_numpy()
    return 2595.0 * np.log10(1.0 + hz / 700.0)

def mel_to_hz(mel):
    return 700.0 * (10 ** (mel / 2595.0) - 1)

def create_mel_filterbank(fft_size, sample_rate, num_mel_bins):
    np = _load_numpy()
    fft_bin_count = fft_size // 2 + 1
    mel_points = np.linspace(hz_to_mel(20), hz_to_mel(sample_rate / 2), num_mel_bins + 2)
    bins = np.floor((fft_size + 1) * mel_to_hz(mel_points) / sample_rate).astype(int)
    filters = []

    for index in range(num_mel_bins):
        start, center, end = bins[index], bins[index + 1], bins[index + 2]
        filterbank = np.zeros(fft_bin_count)
        if center > start:
            filterbank[start:center] = (np.arange(start, center) - start) / (center - start + 1e-6)
        if end > center:
            filterbank[center:end] = (end - np.arange(center, end)) / (end - center + 1e-6)
        filters.append(filterbank)

    return np.array(filters)

def compute_fbank(samples):
    np = _load_numpy()
    frame_length = int(SAMPLE_RATE * 25 / 1000)
    frame_shift = int(SAMPLE_RATE * 10 / 1000)
    fft_size = 1
    while fft_size < frame_length:
        fft_size <<= 1

    frame_count = int((len(samples) - frame_length) / frame_shift) + 1
    if frame_count <= 0:
        return np.empty((0, 80), dtype=np.float32)

    window = hamming(frame_length)
    filters = create_mel_filterbank(fft_size, SAMPLE_RATE, 80)
    feats = np.zeros((frame_count, 80), dtype=np.float32)

    for frame_index in range(frame_count):
        offset = frame_index * frame_shift
        frame = samples[offset:offset + frame_length].astype(np.float64)
        raw_frame = frame.copy()
        prev = samples[offset - 1] if offset > 0 else raw_frame[0]
        frame[0] = raw_frame[0] - PREEMPH * prev
        frame[1:] = raw_frame[1:] - PREEMPH * raw_frame[:-1]

        spectrum = np.fft.rfft(frame * window, n=fft_size)
        power = spectrum.real ** 2 + spectrum.imag ** 2
        feats[frame_index] = np.log(np.maximum(filters @ power[:len(power)], 1e-10))

    return feats

def apply_lfr(feats, window_size, window_shift):
    np = _load_numpy()
    if len(feats) < window_size:
        return np.empty((0,), dtype=np.float32)

    frame_count, dim = feats.shape
    reduced_count = (frame_count - window_size) // window_shift + 1
    output = np.zeros((reduced_count, dim * window_size), dtype=np.float32)

    for index in range(reduced_count):
        output[index] = feats[index * window_shift:index * window_shift + window_size].reshape(-1)

    return output

def decode_logits(logits, tokens, blank_id):
    np = _load_numpy()
    ids = np.argmax(logits[0], axis=-1)
    pieces = []
    previous = -1

    for token_id in ids:
        if token_id == blank_id or token_id == previous:
            previous = token_id
            continue
        previous = token_id
        if token_id >= 4:
            pieces.append(tokens.get(int(token_id), ""))

    text = "".join(pieces)
    text = re.sub(r"<\|[^|]+?\|>", "", text)
    text = text.replace("▁", " ")
    return " ".join(text.split())

def transcribe(session, meta, tokens, audio, lang, itn):
    np = _load_numpy()
    waveform = audio.astype(np.float32)
    if not meta["normalize_samples"]:
        waveform = waveform * 32768.0
    waveform = waveform - waveform.mean()

    feats = compute_fbank(waveform)
    lfr = apply_lfr(feats, meta["window_size"], meta["window_shift"])
    if lfr.shape[0] == 0:
        return ""

    cmvn = (lfr + meta["neg_mean"]) * meta["inv_std"]
    input_names = {item.name for item in session.get_inputs()}
    feeds = {}
    feeds["x" if "x" in input_names else "speech"] = cmvn.reshape(1, cmvn.shape[0], cmvn.shape[1]).astype(np.float32)
    feeds["x_length" if "x_length" in input_names else "speech_lengths"] = np.array([cmvn.shape[0]], dtype=np.int32)
    feeds["language"] = np.array([meta["lang"][lang]], dtype=np.int32)
    feeds["text_norm" if "text_norm" in input_names else "textnorm"] = np.array(
        [meta["with_itn_id"] if itn else meta["without_itn_id"]],
        dtype=np.int32,
    )

    logits = session.run(None, feeds)[0]
    return decode_logits(logits, tokens, meta["blank_id"])

