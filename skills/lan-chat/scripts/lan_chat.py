#!/usr/bin/env python3
"""A dependency-free LAN chat room with file sharing.

Run: python3 scripts/lan_chat.py [--work-dir .] [--port 11567]
Open the printed LAN address on devices connected to the same network.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import shutil
import socket
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


HOST = "0.0.0.0"
DEFAULT_PORT = 11567
MAX_MESSAGES = 200
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
MAX_MULTIPART_OVERHEAD = 64 * 1024
MEMBER_TTL_SECONDS = 45
upload_dir = Path.cwd() / "lan_chat_uploads"

messages: list[dict[str, object]] = []
messages_lock = threading.Lock()
members: dict[str, dict[str, str | float]] = {}
members_lock = threading.Lock()
files: dict[str, dict[str, object]] = {}
files_lock = threading.Lock()

PAGE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>局域网小聊</title><style>
:root { color-scheme:light; font-family:ui-rounded,"SF Pro Rounded",system-ui,-apple-system,sans-serif; }
body { min-height:100dvh; margin:0; background:radial-gradient(circle at 10% 0,#fff7dc 0,transparent 31rem),#f5f3ee; color:#292722; } main { display:flex; flex-direction:column; max-width:900px; height:100dvh; min-height:0; margin:auto; padding:18px 24px 20px; box-sizing:border-box; }
h1 { margin:0; font-size:1.48rem; letter-spacing:-.04em; } .hint { color:#7c7468; margin:4px 0 13px; font-size:.92rem; } #name { width:72px; height:46px; padding:0 9px; line-height:44px; text-align:center; } .layout { display:grid; flex:1; min-height:0; grid-template-columns:132px minmax(0,1fr); gap:14px; }
aside,#messages { background:rgba(255,255,253,.9); border:1px solid #e4dfd5; box-shadow:0 12px 30px rgba(73,59,37,.06); border-radius:18px; padding:14px; } aside { align-self:start; } .chat-column { display:flex; flex-direction:column; min-height:0; } h2 { font-size:.9rem; margin:0 0 11px; letter-spacing:.02em; }
#member-count { color:#938b7e; font-weight:500; } .member { display:grid; grid-template-columns:minmax(0,1fr); gap:2px; border-top:1px solid #efeae1; padding:9px 0; }
.member:first-child { border-top:0; padding-top:0; } .member-name { color:#925424; font-weight:700; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .member-ip,.meta { color:#9b9589; font-size:.78rem; } .member-ip { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#messages { display:flex; flex:1; flex-direction:column; align-items:flex-start; min-height:180px; overflow:auto; padding:13px; } .message-row { display:flex; align-items:flex-start; gap:8px; max-width:100%; margin:7px 0; } .message-row.own { align-self:flex-end; flex-direction:row-reverse; } .avatar { display:grid; place-items:center; flex:none; width:34px; height:34px; background:linear-gradient(135deg,#ffe0ba,#f4a466); color:#783d1a; border-radius:50%; font-size:.76rem; font-weight:800; letter-spacing:-.04em; box-shadow:0 2px 7px rgba(107,69,31,.16); } .message-row.own .avatar { background:linear-gradient(135deg,#ffe9cc,#efae70); color:#7d431c; box-shadow:0 2px 7px rgba(130,78,29,.16); } .message { width:fit-content; max-width:min(68vw,540px); padding:9px 12px; margin:0; background:linear-gradient(135deg,#fffdf8,#f7f2e8); border:1px solid #ebe2d4; border-radius:4px 14px 14px 14px; line-height:1.45; white-space:pre-wrap; overflow-wrap:anywhere; } .message-row.own .message { background:#fff0dc; border-color:#efca9e; border-radius:14px 4px 14px 14px; } .message-row.own .attachment { height:auto; padding:0; background:transparent; border-color:transparent; border-radius:0; } .message-row.own .file-link { color:#99571d; } .message-row.own .file-size { color:#a8774e; } .message-row.own .file-type { background:#ffe0ba; color:#93551d; }
.attachment { display:flex; align-items:center; gap:5px; width:fit-content; max-width:100%; height:20px; padding:0 7px; background:#e8f4ff; color:#216da9; border:1px solid #bdddf6; border-radius:6px; box-sizing:border-box; overflow:hidden; } .file-type { flex:none; padding:1px 3px; background:#d5ebff; color:#286da3; border-radius:3px; font-size:.58rem; font-weight:800; line-height:1.15; } .file-link { color:#216da9; font-size:.73rem; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .file-size { flex:none; color:#4384bb; font-size:.7rem; white-space:nowrap; }
form { display:grid; grid-template-columns:72px minmax(0,1fr) auto; align-items:start; gap:9px; margin-top:14px; } input,textarea,button { border:1px solid #ded7ca; border-radius:12px; padding:12px; font:inherit; min-width:0; box-sizing:border-box; }
input,textarea { background:#fffefd; outline:none; transition:border-color .15s,box-shadow .15s; } input:focus,textarea:focus { border-color:#d8894a; box-shadow:0 0 0 3px rgba(215,112,40,.14); } textarea { min-height:46px; max-height:136px; line-height:1.45; resize:vertical; } button { background:linear-gradient(135deg,#e08338,#cf6220); color:white; border:0; cursor:pointer; font-weight:750; padding-inline:17px; box-shadow:0 5px 12px rgba(188,83,25,.2); } button:hover { filter:brightness(.96); } button:disabled { opacity:.6; cursor:wait; } #send { display:grid; place-items:center; align-self:center; width:40px; height:40px; padding:0; border-radius:50%; } #send svg { width:18px; height:18px; } #send.is-busy svg { animation:send-pulse .8s ease-in-out infinite alternate; } @keyframes send-pulse { to { transform:scale(.72); opacity:.45; } }
.composer { --file-chip-width:0px; position:relative; min-width:0; } #text { width:100%; padding:12px 47px 12px calc(12px + var(--file-chip-width)); } .composer.has-file #text { background:#f7fbff; border-color:#9bc8ed; } .attachment-picker { position:absolute; display:grid; place-items:center; right:6px; top:50%; width:36px; height:36px; transform:translateY(-50%); color:#4384bb; border-radius:9px; cursor:pointer; z-index:2; } .attachment-picker:hover { background:#e5f2fd; color:#1769aa; } .attachment-picker:focus-within { outline:2px solid #72afe0; outline-offset:1px; } .attachment-picker svg { width:19px; height:19px; } .attachment-picker input { position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; }
.file-chip { position:absolute; display:none; align-items:center; gap:4px; left:8px; top:50%; max-width:calc(100% - 56px); height:25px; padding:0 4px 0 8px; transform:translateY(-50%); background:#e8f4ff; color:#216da9; border:1px solid #bdddf6; border-radius:7px; font-size:.76rem; white-space:nowrap; z-index:1; } .composer.has-file .file-chip { display:flex; } .file-chip-name { overflow:hidden; text-overflow:ellipsis; } .file-chip button { display:grid; place-items:center; width:19px; height:19px; min-width:19px; padding:0; background:transparent; color:#327eb9; border-radius:5px; box-shadow:none; font-size:1rem; line-height:1; } .file-chip button:hover { background:#cee7fa; filter:none; } .file-chip button:disabled { cursor:wait; }
 .members-toggle { display:none; } @media(max-width:620px) { main { padding:14px 16px 16px; } h1 { font-size:1.35rem; } .hint { margin-bottom:9px; font-size:.85rem; } #name { width:72px; height:46px; padding:0 9px; font-size:.84rem; line-height:44px; } .layout { grid-template-columns:1fr; grid-template-rows:auto minmax(0,1fr); align-content:stretch; gap:8px; } .layout:not(.members-collapsed) { grid-template-rows:auto auto minmax(0,1fr); } .members-toggle { display:flex; align-items:center; justify-content:space-between; width:100%; padding:9px 12px; background:#fffdfa; color:#5f5140; border:1px solid #e4dfd5; border-radius:12px; box-shadow:none; font-size:.86rem; } .members-toggle:hover { filter:none; background:#fff7e9; } .layout.members-collapsed aside { display:none; } aside { max-height:30dvh; padding:10px 12px; overflow:auto; } .chat-column { min-height:0; } form { grid-template-columns:72px minmax(0,1fr) auto; margin-top:9px; } #messages { min-height:0; } }
</style></head><body><main>
<h1>局域网小聊</h1><p class="hint">同 Wi-Fi 下打开该地址，即可发消息和传文件（单文件最大 2 GB）。</p>
<div id="layout" class="layout members-collapsed"><button id="members-toggle" class="members-toggle" type="button" aria-expanded="false">房间成员 <span id="mobile-member-count"></span></button><aside><h2>房间成员 <span id="member-count"></span></h2><div id="members"></div></aside><div class="chat-column">
<section id="messages" aria-live="polite"></section>
<form id="form"><input id="name" maxlength="2" placeholder="昵称" required><div class="composer"><textarea id="text" maxlength="1000" rows="1" placeholder="说点什么…" title="Enter 发送，Shift+Enter 换行" autocomplete="off"></textarea><div id="file-chip" class="file-chip" aria-live="polite"><span id="file-name" class="file-chip-name"></span><button id="clear-file" type="button" title="移除附件" aria-label="移除附件">×</button></div><label class="attachment-picker" title="选择附件" aria-label="选择附件"><input id="file" type="file"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.4 11.6-8.7 8.7a6 6 0 0 1-8.5-8.5l8.7-8.7a4 4 0 0 1 5.7 5.7l-8.7 8.7a2 2 0 0 1-2.8-2.8l8-8"/></svg></label></div><button id="send" type="submit" aria-label="发送" title="发送"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg></button></form>
</div></div></main><script>
const box=document.querySelector('#messages'), form=document.querySelector('#form'), nameInput=document.querySelector('#name'), textInput=document.querySelector('#text'), fileInput=document.querySelector('#file'), sendButton=document.querySelector('#send'), composer=document.querySelector('.composer'), fileChip=document.querySelector('#file-chip'), fileName=document.querySelector('#file-name'), clearFileButton=document.querySelector('#clear-file');
const membersBox=document.querySelector('#members'), memberCount=document.querySelector('#member-count'), mobileMemberCount=document.querySelector('#mobile-member-count'), layout=document.querySelector('#layout'), membersToggle=document.querySelector('#members-toggle'); let latest='', selectedFile=null;
const memberId=localStorage.lanChatMemberId || `${Date.now()}-${Math.random().toString(36).slice(2)}`; localStorage.lanChatMemberId=memberId;
function formatSize(bytes) { if (bytes < 1024) return `${bytes} B`; const units=['KiB','MiB','GiB']; let value=bytes/1024, unit=0; while(value>=1024 && unit<units.length-1) { value/=1024; unit++; } return `${value.toFixed(value<10?1:0)} ${units[unit]}`; }
function avatarText(name) { return Array.from((name||'访客').trim()).slice(0,2).join('') || '访客'; }
function fileType(filename) { const match=/\.([a-z0-9]{1,5})$/i.exec(filename||''); return match ? match[1].toUpperCase() : 'FILE'; }
function item(message) { const own=message.sender_id===memberId; const row=document.createElement('article'); row.className='message-row'; if(own) row.classList.add('own'); const avatar=document.createElement('div'); avatar.className='avatar'; avatar.textContent=avatarText(message.name); avatar.title=message.name; const bubble=document.createElement('div'); bubble.className='message';
  if(message.kind==='file') { const attachment=document.createElement('div'); attachment.className='attachment'; const type=document.createElement('span'); type.className='file-type'; type.textContent=fileType(message.filename); const link=document.createElement('a'); link.className='file-link'; link.href=message.url; link.textContent=message.filename; link.download=message.filename; const size=document.createElement('span'); size.className='file-size'; size.textContent=formatSize(message.size); attachment.append(type,link,size); bubble.append(attachment); } else { bubble.textContent=message.text; } row.append(avatar,bubble); return row; }
function renderMembers(items) { const count=`(${items.length})`; memberCount.textContent=count; mobileMemberCount.textContent=count; membersBox.replaceChildren(...items.map(member=>{ const el=document.createElement('div'); el.className='member'; const name=document.createElement('div'); name.className='member-name'; name.textContent=member.name; const ip=document.createElement('div'); ip.className='member-ip'; ip.textContent=member.ip; el.append(name,ip); return el; })); }
function showError(text) { window.alert(text); }
function setSendLabel(label='发送') { const busy=label!=='发送'; sendButton.classList.toggle('is-busy',busy); sendButton.title=label; sendButton.setAttribute('aria-label',label); }
function resizeTextInput() { textInput.style.height='auto'; textInput.style.height=`${Math.min(textInput.scrollHeight,136)}px`; }
function updateFileChip() { const file=selectedFile; composer.classList.toggle('has-file',!!file); if(!file) { fileName.textContent=''; composer.style.removeProperty('--file-chip-width'); return; } fileName.textContent=`${file.name} · ${formatSize(file.size)}`; requestAnimationFrame(()=>{ if(selectedFile===file) composer.style.setProperty('--file-chip-width',`${Math.ceil(fileChip.getBoundingClientRect().width+10)}px`); }); }
function selectFile(file) { selectedFile=file||null; updateFileChip(); }
function pastedName(file) { if(file.name) return file.name; const subtype=(file.type.split('/')[1]||'bin').replace(/[^a-z0-9]/gi,'') || 'bin'; const prefix=file.type.startsWith('image/') ? '粘贴图片' : '粘贴文件'; return `${prefix}_${new Date().toISOString().replace(/[:.]/g,'-')}.${subtype}`; }
async function refresh() { try { const [messageResponse,memberResponse]=await Promise.all([fetch('/api/messages'),fetch('/api/members',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:memberId,name:nameInput.value})})]); if(!messageResponse.ok || !memberResponse.ok) return; const data=await messageResponse.json(), memberData=await memberResponse.json(); renderMembers(memberData.members||[]); const stamp=JSON.stringify(data); if(stamp!==latest) { const atBottom=box.scrollHeight-box.scrollTop-box.clientHeight<80; box.replaceChildren(...data.map(item)); latest=stamp; if(atBottom||!box.dataset.loaded) box.scrollTop=box.scrollHeight; box.dataset.loaded='yes'; } } catch (_) {} }
form.addEventListener('submit',async event=>{ event.preventDefault(); const name=nameInput.value.trim(), text=textInput.value, file=selectedFile; if(!name) { showError('请先填写昵称。'); nameInput.focus(); return; } if(!text.trim() && !file) { showError('写句话或选择一个文件。'); return; } sendButton.disabled=true; fileInput.disabled=true; clearFileButton.disabled=true; setSendLabel('发送中…'); try { if(text.trim()) { const response=await fetch('/api/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,text,member_id:memberId})}); if(!response.ok) throw new Error((await response.json()).error||'消息发送失败'); textInput.value=''; resizeTextInput(); }
  if(file) { setSendLabel('上传中…'); const formData=new FormData(); formData.append('name',name); formData.append('member_id',memberId); formData.append('file',file,file.name); const response=await fetch('/api/files',{method:'POST',body:formData}); if(!response.ok) { let detail={}; try { detail=await response.json(); } catch (_) {} throw new Error(detail.error||'文件上传失败'); } fileInput.value=''; selectFile(null); }
  localStorage.lanChatName=name; await refresh(); } catch(error) { showError(error.message||'发送失败。'); } finally { sendButton.disabled=false; fileInput.disabled=false; clearFileButton.disabled=false; setSendLabel(); } });
nameInput.addEventListener('input',()=>localStorage.lanChatName=nameInput.value.trim()); fileInput.addEventListener('change',()=>selectFile(fileInput.files[0])); textInput.addEventListener('input',resizeTextInput); textInput.addEventListener('keydown',event=>{ if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing) { event.preventDefault(); form.requestSubmit(); } }); textInput.addEventListener('paste',event=>{ const clipboard=event.clipboardData; const item=[...clipboard.items].find(candidate=>candidate.kind==='file'); const file=item&&item.getAsFile(); if(!file) return; event.preventDefault(); const named=new File([file],pastedName(file),{type:file.type||'application/octet-stream'}); selectFile(named); }); clearFileButton.addEventListener('click',()=>{ fileInput.value=''; selectFile(null); textInput.focus(); }); membersToggle.addEventListener('click',()=>{ const collapsed=layout.classList.toggle('members-collapsed'); membersToggle.setAttribute('aria-expanded',String(!collapsed)); }); if(matchMedia('(max-width:620px)').matches) layout.classList.add('members-collapsed'); nameInput.value=localStorage.lanChatName||''; resizeTextInput(); refresh(); setInterval(refresh,3000);
</script></body></html>"""


def local_address() -> str:
    """Find the outward-facing LAN address without sending network traffic."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_filename(filename: str) -> str:
    """Keep a display filename, without accepting a client-controlled path."""
    name = Path(filename.replace("\\", "/")).name.replace("\x00", "").strip()
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name)[:120]
    return name or "未命名文件"


def set_upload_dir(work_dir: Path) -> None:
    global upload_dir
    upload_dir = work_dir.resolve() / "lan_chat_uploads"


def cleanup_uploaded_files() -> None:
    """Remove files received during this temporary chat session."""
    with files_lock:
        files.clear()
    if upload_dir.exists():
        shutil.rmtree(upload_dir)


class MultipartReader:
    """A small, bounded multipart reader that streams file bytes to disk."""

    def __init__(self, source: object, remaining: int) -> None:
        self.source = source
        self.remaining = remaining
        self.buffer = b""

    def read(self, size: int) -> bytes:
        if size <= 0:
            return b""
        prefix = self.buffer[:size]
        self.buffer = self.buffer[len(prefix):]
        if len(prefix) == size or self.remaining <= 0:
            return prefix
        chunk = self.source.read(min(size - len(prefix), self.remaining))
        self.remaining -= len(chunk)
        return prefix + chunk

    def readline(self, limit: int = 8192) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while total < limit:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                line = self.buffer[:newline + 1]
                self.buffer = self.buffer[newline + 1:]
                return b"".join(chunks) + line
            if self.buffer:
                chunks.append(self.buffer)
                total += len(self.buffer)
                self.buffer = b""
            if self.remaining <= 0:
                return b"".join(chunks)
            chunk = self.source.readline(limit - total)
            self.remaining -= len(chunk)
            chunks.append(chunk)
            total += len(chunk)
            if chunk.endswith(b"\n") or not chunk:
                return b"".join(chunks)
        raise ValueError("multipart header is too long")

    def headers(self) -> dict[str, bytes]:
        result: dict[str, bytes] = {}
        while True:
            line = self.readline()
            if line == b"\r\n":
                return result
            if not line.endswith(b"\r\n") or b":" not in line:
                raise ValueError("invalid multipart headers")
            key, value = line[:-2].split(b":", 1)
            result[key.decode("ascii", "ignore").lower()] = value.strip()

    def read_part(self, boundary: bytes, limit: int | None = None,
                  write_chunk: object | None = None) -> bytes:
        delimiter = b"\r\n--" + boundary
        keep = len(delimiter) - 1
        tail = b""
        value = bytearray()
        count = 0

        def consume(chunk: bytes) -> None:
            nonlocal count
            count += len(chunk)
            if limit is not None and count > limit:
                raise ValueError("multipart field is too large")
            if write_chunk is None:
                value.extend(chunk)
            else:
                write_chunk(chunk)

        while True:
            chunk = self.read(64 * 1024)
            if not chunk:
                raise ValueError("unterminated multipart body")
            data = tail + chunk
            position = data.find(delimiter)
            if position >= 0:
                consume(data[:position])
                self.buffer = data[position + len(delimiter):] + self.buffer
                return bytes(value)
            if len(data) > keep:
                consume(data[:-keep])
                tail = data[-keep:]
            else:
                tail = data

    def finish_part(self) -> bool:
        suffix = self.read(2)
        if suffix == b"\r\n":
            return False
        if suffix == b"--":
            ending = self.read(2)
            if ending not in {b"", b"\r\n"}:
                raise ValueError("invalid multipart ending")
            return True
        raise ValueError("invalid multipart boundary")


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # 失败响应统一走这里：写结构化日志（含客户端 IP），再返回 JSON，便于远端定位
    def fail_json(self, status: HTTPStatus, reason: str, **extra: object) -> None:
        detail = " ".join(f"{k}={v}" for k, v in extra.items())
        print(f"[lan-chat] /api/files {self.client_ip()} -> {status.value} {reason}{(' ' + detail) if detail else ''}", flush=True)
        self.send_json({"error": reason, **extra}, status)

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 4096:
            raise ValueError
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError
        return data

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        return forwarded.split(",", 1)[0].strip() if forwarded else self.client_address[0]

    def active_members(self) -> list[dict[str, str]]:
        cutoff = time.monotonic() - MEMBER_TTL_SECONDS
        with members_lock:
            stale_ids = [key for key, value in members.items() if float(value["last_seen"]) < cutoff]
            for key in stale_ids:
                del members[key]
            return [{"name": str(value["name"]), "ip": str(value["ip"])}
                    for value in sorted(members.values(), key=lambda value: str(value["name"]).lower())]

    def add_message(self, message: dict[str, object]) -> None:
        with messages_lock:
            messages.append(message)
            del messages[:-MAX_MESSAGES]

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/messages":
            with messages_lock:
                self.send_json(messages)
        elif path == "/api/members":
            self.send_json({"members": self.active_members()})
        elif path.startswith("/files/"):
            self.serve_file(unquote(path.removeprefix("/files/")))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def serve_file(self, file_id: str) -> None:
        with files_lock:
            record = files.get(file_id)
        if not record:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        disk_path = Path(str(record["path"]))
        try:
            size = disk_path.stat().st_size
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename = str(record["filename"])
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(filename))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            with disk_path.open("rb") as source:
                shutil.copyfileobj(source, self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/files":
            self.receive_file()
            return
        if path not in {"/api/messages", "/api/members"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            data = self.read_json()
        except (TypeError, ValueError, json.JSONDecodeError):
            self.send_json({"error": "请求内容无效"}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/members":
            member_id = str(data.get("id", "")).strip()[:128]
            name = str(data.get("name", "")).strip()[:2] or "访客"
            if not member_id:
                self.send_json({"error": "成员标识不能为空"}, HTTPStatus.BAD_REQUEST)
                return
            with members_lock:
                members[member_id] = {"name": name, "ip": self.client_ip(), "last_seen": time.monotonic()}
            self.send_json({"members": self.active_members()})
            return
        name = str(data.get("name", "")).strip()[:2]
        text = str(data.get("text", "")).replace("\r\n", "\n").replace("\r", "\n")[:1000]
        sender_id = str(data.get("member_id", "")).strip()[:128]
        if not name or not text.strip():
            self.send_json({"error": "昵称和消息不能为空"}, HTTPStatus.BAD_REQUEST)
            return
        message = {"kind": "text", "name": name, "text": text, "sender_id": sender_id, "time": now()}
        self.add_message(message)
        self.send_json(message, HTTPStatus.CREATED)

    def receive_file(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        match = re.fullmatch(r"multipart/form-data;\s*boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type, re.I)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not match:
            self.fail_json(HTTPStatus.BAD_REQUEST, "文件上传格式无效：缺少 multipart boundary")
            return
        if not 0 < length <= MAX_UPLOAD_BYTES + MAX_MULTIPART_OVERHEAD:
            self.fail_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "请选择不超过 2 GiB 的文件", content_length=length)
            return
        boundary = (match.group(1) or match.group(2)).encode("ascii", "strict")
        reader = MultipartReader(self.rfile, length)
        if reader.readline() != b"--" + boundary + b"\r\n":
            self.fail_json(HTTPStatus.BAD_REQUEST, "文件上传格式无效：boundary 首行不匹配")
            return
        name = ""
        sender_id = ""
        filename = ""
        temp_path: Path | None = None
        file_size = 0
        try:
            final_part = False
            while not final_part:
                headers = reader.headers()
                disposition = headers.get("content-disposition", b"")
                field = re.search(br'\bname="([^"]+)"', disposition)
                if not field:
                    raise ValueError("multipart 字段缺少 name")
                field_name = field.group(1).decode("utf-8", "replace")
                if field_name == "name":
                    value = reader.read_part(boundary, MAX_MULTIPART_OVERHEAD)
                    name = value.decode("utf-8", "replace").strip()[:2]
                    final_part = reader.finish_part()
                elif field_name == "member_id":
                    value = reader.read_part(boundary, MAX_MULTIPART_OVERHEAD)
                    sender_id = value.decode("utf-8", "replace").strip()[:128]
                    final_part = reader.finish_part()
                elif field_name == "file":
                    filename_match = re.search(br'\bfilename="([^"]*)"', disposition)
                    if not filename_match or temp_path is not None:
                        raise ValueError("file 字段缺少 filename 或重复上传")
                    filename = filename_match.group(1).decode("utf-8", "replace")
                    upload_dir.mkdir(mode=0o700, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=upload_dir, prefix=".upload-", delete=False) as target:
                        temp_path = Path(target.name)

                        def write_chunk(chunk: bytes) -> None:
                            nonlocal file_size
                            file_size += len(chunk)
                            if file_size > MAX_UPLOAD_BYTES:
                                raise OverflowError
                            target.write(chunk)

                        reader.read_part(boundary, write_chunk=write_chunk)
                    final_part = reader.finish_part()
                else:
                    reader.read_part(boundary, MAX_MULTIPART_OVERHEAD)
                    final_part = reader.finish_part()
            if reader.remaining != 0:
                raise ValueError("multipart body 未完整读取")
            if not name or temp_path is None or not filename:
                raise ValueError("昵称和文件不能为空")
        except OverflowError:
            if temp_path:
                temp_path.unlink(missing_ok=True)
            self.fail_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "文件不能超过 2 GiB")
            return
        except (OSError, ValueError) as error:
            if temp_path:
                temp_path.unlink(missing_ok=True)
            self.fail_json(HTTPStatus.BAD_REQUEST, str(error) or "文件上传解析失败")
            return
        file_id = uuid.uuid4().hex
        display_name = safe_filename(filename)
        disk_path = upload_dir / file_id
        temp_path.replace(disk_path)
        record = {"path": str(disk_path), "filename": display_name, "size": file_size}
        with files_lock:
            files[file_id] = record
        message = {"kind": "file", "name": name, "sender_id": sender_id, "filename": display_name, "size": file_size,
                   "url": f"/files/{file_id}", "time": now()}
        self.add_message(message)
        self.send_json(message, HTTPStatus.CREATED)


def parse_args() -> tuple[int, Path]:
    parser = argparse.ArgumentParser(description="零依赖局域网聊天室")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path.cwd(),
        help="工作区，上传文件存入其下 lan_chat_uploads/",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"监听端口，默认 {DEFAULT_PORT}",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口须在 1–65535 之间")
    return args.port, args.work_dir.resolve()


if __name__ == "__main__":
    port, work_dir = parse_args()
    set_upload_dir(work_dir)
    cleanup_uploaded_files()
    server = ThreadingHTTPServer((HOST, port), ChatHandler)

    def stop_on_signal(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_on_signal)
    signal.signal(signal.SIGINT, stop_on_signal)
    print(f"局域网聊天已启动：http://{local_address()}:{port}", flush=True)
    print("按 Ctrl+C 停止服务。停服时会自动清理聊天记录和接收的文件。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n聊天服务已停止。", flush=True)
    finally:
        server.server_close()
        cleanup_uploaded_files()
