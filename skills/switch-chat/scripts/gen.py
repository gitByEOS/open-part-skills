#!/usr/bin/env python3
"""生成可编辑的交接可视化 HTML。用法: python3 gen.py [output.html] [--open] [--from handoff.md]"""

import re
import sys
import json as _json
import webbrowser
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_HANDOFF_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'continue.html'
IDLE_TIMEOUT_SECONDS = 300


def parse_sections(content: str) -> list[dict]:
    """解析 Markdown 中的二级标题分段"""
    icons = {
        '工作目标': '📋', '当前进度': '🚧', '待办事项': '📝',
        '关键决策': '⚡', '关键文件': '📁', '注意事项': '⚠️',
        '已完成工作': '✅', '未完成项': '❌',
    }

    sections = {}
    current_key = None
    current_lines = []

    for line in content.split('\n'):
        m = re.match(r'^##\s+(.+)$', line.strip())
        if m:
            if current_key:
                sections[current_key] = '\n'.join(current_lines).strip()
            current_key = m.group(1).strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key:
        sections[current_key] = '\n'.join(current_lines).strip()

    result = []
    section_order = ['工作目标', '当前进度', '待办事项', '关键决策', '关键文件', '注意事项']
    ordered_keys = [k for k in section_order if k in sections]
    other_keys = [k for k in sections if k not in section_order]
    ordered_keys.extend(other_keys)

    for key in ordered_keys:
        body = sections[key]
        items = []
        paragraphs = []
        for line in body.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('- [x] '):
                items.append({'type': 'done', 'text': line[6:]})
            elif line.startswith('- [ ] '):
                items.append({'type': 'todo', 'text': line[6:]})
            elif line.startswith('- '):
                items.append({'type': 'text', 'text': line[2:]})
            else:
                paragraphs.append(line)
        result.append({
            'title': key,
            'icon': icons.get(key, '✏️'),
            'paragraphs': paragraphs,
            'items': items,
        })

    return result


def gen_html(title: str, sections: list[dict], save_endpoint: str = '') -> str:
    sections_json = _json.dumps(sections, ensure_ascii=False)
    save_endpoint_json = _json.dumps(save_endpoint, ensure_ascii=False)

    return f'''<!doctype html>
<html lang="zh">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
:root {{
  --bg:#080b13;
  --panel:#111827;
  --panel-strong:#172033;
  --panel-soft:#0d1320;
  --line:#253044;
  --line-soft:rgba(148,163,184,0.14);
  --text:#e5edf8;
  --muted:#7f8da3;
  --muted-strong:#a8b3c7;
  --blue:#60a5fa;
  --blue-strong:#38bdf8;
  --green:#22c55e;
  --yellow:#f59e0b;
  --red:#ef4444;
  --red-bg:rgba(127,29,29,0.42);
  --shadow:0 24px 80px rgba(0,0,0,0.38);
}}
body {{
  font-family:"Noto Sans SC",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#0d1117;
  color:#cdd6f4;
  padding:40px 20px 80px;
  line-height:1.7;
}}
.container {{ max-width:900px; margin:0 auto; }}
header {{
  position:relative;
  padding:10px 18px 12px;
  margin-bottom:34px;
  overflow:hidden;
  text-align:center;
  border:1px solid var(--line-soft);
  border-radius:10px;
  background:linear-gradient(145deg,rgba(17,24,39,0.94),rgba(15,23,42,0.76));
  box-shadow:var(--shadow);
}}
header::before {{
  position:absolute;
  inset:0;
  pointer-events:none;
  content:"";
  background:linear-gradient(90deg,transparent,rgba(96,165,250,0.16),transparent);
  transform:translateX(-45%);
}}
#mainTitle {{
  position:relative;
  width:100%;
  padding:4px 12px;
  border:1px solid transparent;
  border-radius:8px;
  background:none;
  color:#f8fafc;
  font-family:inherit;
  font-size:28px;
  font-weight:800;
  letter-spacing:-0.03em;
  text-align:center;
  text-shadow:0 0 30px rgba(56,189,248,0.28);
  transition:background 0.18s,border-color 0.18s;
}}
#mainTitle:hover, #mainTitle:focus {{ border-color:rgba(96,165,250,0.42); outline:none; background:rgba(15,23,42,0.58); }}
.meta {{ position:relative; color:var(--muted-strong); font-size:13px; }}

/* toolbar */
.toolbar {{
  display:flex; gap:8px; justify-content:center; margin-bottom:28px; flex-wrap:wrap;
}}
.toolbar button {{
  background:#21262d; color:#cdd6f4; border:1px solid #30363d; border-radius:8px;
  padding:8px 16px; font-size:13px; cursor:pointer; font-family:inherit; transition:all 0.15s;
}}
.toolbar button:hover {{ background:#30363d; }}
.toolbar button.save {{ background:#238636; border-color:#2ea043; color:#fff; }}
.toolbar button.save:hover {{ background:#2ea043; }}

/* section */
.section {{
  background:#161b22; border:1px solid #21262d; border-radius:10px;
  margin-bottom:16px; overflow:hidden;
}}
.s-head {{
  display:flex;
  align-items:center;
  gap:8px;
  padding:12px 16px;
  border-bottom:1px solid var(--line-soft);
  background:linear-gradient(90deg,rgba(30,41,59,0.84),rgba(15,23,42,0.72));
}}
.s-ico {{
  font-size:18px; cursor:default;
}}
.s-title {{
  flex:1; background:none; border:1px solid transparent; border-radius:6px;
  color:#cdd6f4; font-size:15px; font-weight:600; font-family:inherit;
  padding:2px 8px;
}}
.s-title:hover {{ border-color:#30363d; }}
.s-title:focus {{ border-color:#58a6ff; outline:none; background:#0d1117; }}

.s-add {{
  background:none; border:1px dashed #30363d; border-radius:6px;
  color:#484f58; cursor:pointer; font-size:18px; width:28px; height:28px;
  display:flex; align-items:center; justify-content:center;
}}
.s-add:hover {{ color:#58a6ff; border-color:#58a6ff; }}
.s-del {{
  background:none; border:none; color:#484f58; cursor:pointer;
  font-size:18px; width:28px; height:28px;
  display:flex; align-items:center; justify-content:center; border-radius:6px;
}}
.s-del:hover {{ color:#f85149; background:#3d1416; }}

.content {{ padding:12px 16px; }}
.content:empty::before {{ content:"点击右侧 ＋ 添加内容"; color:#30363d; display:block; padding:8px 0; }}

/* row */
.row {{
  display:flex; align-items:center; gap:6px; margin-bottom:6px;
  padding:6px 10px; border-radius:6px; background:#0d1117;
  border-left:3px solid #30363d;
}}
.row:hover .row-del {{ opacity:1; }}
.row.done {{ border-left-color:#238636; }}
.row.done .row-text {{ text-decoration:line-through; color:#6c7086; }}
.row.todo {{ border-left-color:#d29922; }}
.row.para {{ border-left-color:#58a6ff; }}
.section.goal .row {{ border-left-color:#58a6ff; }}
.section.progress .row.done {{ border-left-color:#238636; }}
.section.progress .row.todo {{ border-left-color:#d29922; }}
.section.todos .row {{ border-left-color:#d29922; }}
.section.decision .row {{ border-left-color:#a371f7; }}
.section.files .row {{ border-left-color:#39c5cf; }}
.section.note .row {{ border-left-color:#f85149; }}

.row-text {{
  flex:1; background:none; border:1px solid transparent; border-radius:4px;
  color:#cdd6f4; font-size:14px; font-family:inherit; padding:2px 6px;
  line-height:1.6; resize:none; overflow:hidden; min-height:24px;
}}
.row-text:hover {{ border-color:#30363d; }}
.row-text:focus {{ border-color:#58a6ff; outline:none; background:#1c2128; }}

.row-toggle {{
  width:26px; height:26px; border-radius:50%; border:none; background:none;
  cursor:pointer; color:#484f58; font-size:14px; display:flex;
  align-items:center; justify-content:center; flex-shrink:0;
}}
.row.done .row-toggle {{ color:#238636; }}
.row.todo .row-toggle {{ color:#d29922; }}

.row-del {{
  color:#f85149; background:none; border:none;
  cursor:pointer; font-size:13px; padding:4px 8px; flex-shrink:0;
  font-family:inherit; border-radius:4px; opacity:0; transition:opacity 0.15s;
}}
.row:hover .row-del {{ opacity:1; }}
.row-del:hover {{ background:#3d1416; }}

/* add section */
.add-section {{
  border:2px dashed #21262d; border-radius:10px; padding:20px;
  text-align:center; cursor:pointer; color:#484f58; font-size:14px;
  margin-bottom:20px; transition:all 0.2s;
}}
.add-section:hover {{ border-color:#30363d; color:#6c7086; }}

footer {{ text-align:center; padding:32px 0 0; color:#30363d; font-size:12px; }}

/* toast */
.toast {{
  position:fixed; bottom:24px; left:50%; transform:translateX(-50%) translateY(60px);
  background:#238636; color:#fff; padding:10px 24px; border-radius:8px;
  font-size:14px; opacity:0; transition:all 0.3s; z-index:999;
  pointer-events:none;
}}
.toast.show {{ transform:translateX(-50%) translateY(0); opacity:1; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <input id="mainTitle" value="{title}" />
    <p class="meta">任务交接文档 · 直接编辑内容，随时保存</p>
  </header>
  <div class="toolbar">
    <button class="save" onclick="writeBack()">回写</button>
    <button onclick="saveMd()">复制</button>
    <button onclick="autoSave()">导出文件</button>
  </div>
  <div id="sectionsRoot"></div>
  <div class="add-section" onclick="addSection()">＋ 添加新区块</div>
  <footer>switch-chat skill</footer>
</div>
<div id="toast" class="toast"></div>

<script>
var SECTIONS = {sections_json};
var FILE_PATH = null;
var SAVE_ENDPOINT = {save_endpoint_json};
var CONTINUE_COMMAND = '/switch-chat 继续';

function uid() {{ return Date.now().toString(36) + Math.random().toString(36).slice(2,7); }}

function sectionClass(title) {{
  var map = {{
    '工作目标':'goal',
    '当前进度':'progress',
    '待办事项':'todos',
    '关键决策':'decision',
    '关键文件':'files',
    '注意事项':'note'
  }};
  return map[title] || 'other';
}}

function render() {{
  var root = document.getElementById('sectionsRoot');
  root.innerHTML = '';
  SECTIONS.forEach(function(sec, si) {{
    var el = document.createElement('div');
    el.className = 'section ' + sectionClass(sec.title);
    el.dataset.si = si;

    var rows = '';
    (sec.paragraphs || []).forEach(function(p, pi) {{
      rows += '<div class="row para" data-si="'+si+'" data-pi="'+pi+'">'
        + '<textarea class="row-text" rows="1" oninput="autoResize(this)" onblur="syncEdit(this)">'+esc(p)+'</textarea>'
        + '<button class="row-del" onclick="delRow('+si+',0,'+pi+')">[删除]</button></div>';
    }});
    (sec.items || []).forEach(function(it, ii) {{
      var ch = it.type === 'done' ? '✓' : it.type === 'todo' ? '○' : '';
      var toggle = ch ? '<button class="row-toggle" onclick="toggleType('+si+','+ii+')">'+ch+'</button>' : '';
      rows += '<div class="row '+it.type+'" data-si="'+si+'" data-ii="'+ii+'">'
        + toggle
        + '<textarea class="row-text" rows="1" oninput="autoResize(this)" onblur="syncEdit(this)">'+esc(it.text)+'</textarea>'
        + '<button class="row-del" onclick="delRow('+si+',1,'+ii+')">[删除]</button></div>';
    }});

    el.innerHTML = '<div class="s-head">'
      + '<span class="s-ico">'+sec.icon+'</span>'
      + '<input class="s-title" value="'+esc(sec.title)+'" onblur="syncTitle('+si+',this)" onkeydown="if(event.key===\\'Enter\\')this.blur()"/>'
      + '<button class="s-add" onclick="addRow('+si+')" title="添加行">＋</button>'
      + '<button class="s-del" onclick="delSection('+si+')" title="删除区块">×</button></div>'
      + '<div class="content">'+rows+'</div>';
    root.appendChild(el);
  }});
  // resize all textareas
  document.querySelectorAll('.row-text').forEach(function(ta) {{ autoResize(ta); }});
}}

function esc(s) {{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

function autoResize(ta) {{
  ta.style.height = 'auto';
  ta.style.height = ta.scrollHeight + 'px';
}}

function syncTitle(si, input) {{ SECTIONS[si].title = input.value.trim(); }}

function syncEdit(ta) {{
  var row = ta.parentElement;
  var si = parseInt(row.dataset.si);
  if (row.dataset.pi !== undefined) {{
    SECTIONS[si].paragraphs[parseInt(row.dataset.pi)] = ta.value.trim();
  }} else {{
    SECTIONS[si].items[parseInt(row.dataset.ii)].text = ta.value.trim();
  }}
}}

function syncAllEdits() {{
  document.querySelectorAll('.s-title').forEach(function(input) {{
    var section = input.closest('.section');
    if (section) syncTitle(parseInt(section.dataset.si), input);
  }});
  document.querySelectorAll('.row-text').forEach(function(ta) {{
    syncEdit(ta);
  }});
}}

function toggleType(si, ii) {{
  var it = SECTIONS[si].items[ii];
  it.type = it.type === 'done' ? 'todo' : it.type === 'todo' ? 'done' : it.type;
  render();
}}

function delRow(si, type, idx) {{
  if (type === 0) SECTIONS[si].paragraphs.splice(idx, 1);
  else SECTIONS[si].items.splice(idx, 1);
  render();
}}

function delSection(si) {{
  SECTIONS.splice(si, 1);
  render();
}}

function addRow(si) {{
  SECTIONS[si].items.push({{type:'todo', text:'', _id: uid()}});
  render();
  // focus the new textarea
  setTimeout(function() {{
    var rows = document.querySelectorAll('.section[data-si="'+si+'"] .row-text');
    if (rows.length) rows[rows.length-1].focus();
  }}, 0);
}}

function addSection() {{
  SECTIONS.push({{title:'新段落', icon:'✏️', paragraphs:[], items:[]}});
  render();
}}

function buildMd() {{
  var lines = ['# ' + document.getElementById('mainTitle').value.trim(), ''];
  SECTIONS.forEach(function(sec) {{
    lines.push('## ' + sec.title, '');
    (sec.paragraphs||[]).forEach(function(p) {{ if(p) lines.push(p, ''); }});
    (sec.items||[]).forEach(function(it) {{
      if (it.type === 'done') lines.push('- [x] ' + it.text);
      else if (it.type === 'todo') lines.push('- [ ] ' + it.text);
      else if (it.text) lines.push('- ' + it.text);
    }});
    lines.push('');
  }});
  return lines.join('\\n');
}}

function autoSave() {{
  var md = buildMd();
  var blob = new Blob([md], {{type:'text/markdown'}});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'switch-chat.md';
  a.click();
  URL.revokeObjectURL(a.href);
  toast('已下载文件');
}}

function saveMd() {{
  var md = buildMd();
  if (navigator.clipboard) {{
    navigator.clipboard.writeText(md).then(function() {{ toast('已复制到剪贴板'); }})
      }} else {{
    // fallback copy with textarea
    var ta = document.createElement('textarea');
    ta.value = md; ta.style.position='fixed'; ta.style.left='-9999px';
    document.body.appendChild(ta); ta.select();
    try {{ document.execCommand('copy'); toast('已复制到剪贴板'); }}
    catch(e) {{ toast('复制失败'); }}
    ta.remove();
  }}
}}

function copyContinueCommand(message) {{
  if (navigator.clipboard) {{
    navigator.clipboard.writeText(CONTINUE_COMMAND).then(function() {{ toast(message); }});
    return;
  }}
  var ta = document.createElement('textarea');
  ta.value = CONTINUE_COMMAND; ta.style.position='fixed'; ta.style.left='-9999px';
  document.body.appendChild(ta); ta.select();
  try {{ document.execCommand('copy'); toast(message); }}
  catch(e) {{ toast('已回写，复制继续命令失败'); }}
  ta.remove();
}}

function writeBack() {{
  syncAllEdits();
  if (!SAVE_ENDPOINT) {{
    toast('请用 --open 启动回写服务');
    return;
  }}
  fetch(SAVE_ENDPOINT, {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{
      title:document.getElementById('mainTitle').value.trim(),
      sections:SECTIONS
    }})
  }}).then(function(res) {{
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }}).then(function() {{
    copyContinueCommand('新会话粘贴即可');
  }}).catch(function() {{
    toast('回写失败');
  }});
}}

function toast(msg) {{
  var el = document.getElementById('toast');
  el.textContent = msg; el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(function() {{ el.classList.remove('show'); }}, 2000);
}}

document.getElementById('mainTitle').addEventListener('blur', function() {{
  document.title = this.value.trim();
}});

render();
</script>
</body>
</html>'''


def start_save_server(out_path: Path) -> tuple[ThreadingHTTPServer, str]:
    endpoint = {'value': ''}
    last_active = {'value': time.monotonic()}

    class SaveHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def send_cors_headers(self) -> None:
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_cors_headers()
            self.end_headers()

        def do_POST(self) -> None:
            last_active['value'] = time.monotonic()
            if self.path != '/save':
                self.send_response(404)
                self.send_cors_headers()
                self.end_headers()
                return

            length = int(self.headers.get('Content-Length', '0'))
            try:
                payload = _json.loads(self.rfile.read(length).decode('utf-8'))
                title = str(payload.get('title') or '任务交接').strip()
                sections = payload.get('sections')
                if not isinstance(sections, list):
                    raise ValueError('sections must be a list')

                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(gen_html(title, sections, endpoint['value']), encoding='utf-8')
                body = _json.dumps({'ok': True, 'path': str(out_path)}, ensure_ascii=False).encode('utf-8')
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as error:
                body = _json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False).encode('utf-8')
                self.send_response(400)
                self.send_cors_headers()
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), SaveHandler)
    server.timeout = 1
    server.last_active = last_active
    endpoint['value'] = f'http://127.0.0.1:{server.server_port}/save'
    return server, endpoint['value']


def main():
    args = []
    should_open = False
    from_file = None

    raw_args = sys.argv[1:]
    index = 0
    while index < len(raw_args):
        arg = raw_args[index]
        if arg == '--open':
            should_open = True
        elif arg.startswith('--from='):
            from_file = arg.split('=', 1)[1]
        elif arg == '--from':
            if index + 1 >= len(raw_args):
                print("--from 需要文件路径")
                sys.exit(1)
            from_file = raw_args[index + 1]
            index += 1
        else:
            args.append(arg)
        index += 1

    out_path = None
    if args:
        out_path = Path(args[0])
    else:
        out_path = DEFAULT_HANDOFF_PATH

    title = '任务交接'
    sections = []
    content = ''

    # 优先读取 --from 文件，其次读取 stdin（heredoc）
    if from_file:
        in_path = Path(from_file)
        if not in_path.is_file():
            print(f"文件不存在: {from_file}")
            sys.exit(1)
        content = in_path.read_text(encoding='utf-8')
    elif not sys.stdin.isatty():
        content = sys.stdin.read()

    if content:
        m = re.match(r'^#\s+(.+)$', content.strip(), re.MULTILINE)
        title = m.group(1).strip() if m else title
        body = re.sub(r'^#\s+.+$', '', content, count=1, flags=re.MULTILINE).strip()
        sections = parse_sections(body)

    save_server = None
    save_endpoint = ''
    if should_open:
        save_server, save_endpoint = start_save_server(out_path)

    html = gen_html(title, sections, save_endpoint)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding='utf-8')
    print(f"已生成: {out_path}")

    if should_open:
        webbrowser.open(out_path.resolve().as_uri())
        print("已在浏览器中打开")
        print(f"回写服务: {save_endpoint}")
        print("保持此进程运行，页面才能回写 continue.html。5 分钟无回写会自动结束。")
        try:
            while time.monotonic() - save_server.last_active['value'] < IDLE_TIMEOUT_SECONDS:
                save_server.handle_request()
            print("\n5 分钟无回写，已停止回写服务")
        except KeyboardInterrupt:
            print("\n已停止回写服务")
        finally:
            save_server.server_close()


if __name__ == '__main__':
    main()
