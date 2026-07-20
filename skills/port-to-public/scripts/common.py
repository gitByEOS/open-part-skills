"""port-to-public 的共享校验、状态和 Cloudflare Quick Tunnel 工具。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from esflow import CheckResult


def _warn(message: str) -> None:
    # chmod 在跨平台/特殊文件系统下可能失败，留痕但不阻断流程。
    print(f"[port-to-public] {message}", file=sys.stderr)


TOOL_NAME = "port-to-public"
SCHEMA_VERSION = "1.0.0"
DEFAULT_TTL = 12 * 60 * 60
MAX_TTL = 24 * 60 * 60
DEFAULT_TIMEOUT = 120
DEFAULT_VERIFY_TIMEOUT = 20
URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
VALID_ACTIONS = frozenset({"start", "status", "verify", "stop"})


class CliError(Exception):
    """具备稳定机器码的命令行错误。"""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def json_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, CliError):
        return {"code": exc.code, "message": exc.message, "retryable": exc.retryable}
    return {
        "code": "unexpected",
        "message": f"{type(exc).__name__}: {exc}",
        "retryable": False,
    }


def check_cloudflared() -> CheckResult | None:
    if shutil.which("cloudflared"):
        return None
    return CheckResult(
        reason="未找到 cloudflared",
        fix="安装 Cloudflare Tunnel：brew install cloudflared",
    )


def normalize_target(port: int | None, raw_url: str | None) -> str:
    if (port is None) == (raw_url is None):
        raise CliError("invalid_target", "必须且只能提供 --port 或 --url")

    if port is not None:
        if not 1 <= port <= 65535:
            raise CliError("invalid_port", f"端口必须在 1-65535 之间：{port}")
        return f"http://127.0.0.1:{port}"

    assert raw_url is not None
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise CliError("invalid_target", "--url 仅支持 http 或 https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CliError("invalid_target", "--url 不允许账号、query 或 fragment")
    if parsed.path not in {"", "/"}:
        raise CliError("invalid_target", "--url 不允许路径，请用 --path 验证公网路径")
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise CliError("unsafe_target", "仅允许暴露 loopback 地址：localhost、127.0.0.1、::1")
    try:
        port_number = parsed.port
    except ValueError as exc:
        raise CliError("invalid_target", f"--url 端口无效：{exc}") from exc
    if port_number is None:
        port_number = 443 if parsed.scheme == "https" else 80
    if not 1 <= port_number <= 65535:
        raise CliError("invalid_port", f"端口必须在 1-65535 之间：{port_number}")
    host_text = "[::1]" if host == "::1" else host
    return f"{parsed.scheme}://{host_text}:{port_number}"


def normalize_public_path(raw_path: str | None) -> str:
    path = raw_path or "/"
    if not path.startswith("/") or path.startswith("//"):
        raise CliError("invalid_path", "--path 必须是以单个 / 开头的同源相对路径")
    if any(ord(char) < 32 for char in path) or "\\" in path:
        raise CliError("invalid_path", "--path 含非法控制字符")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc:
        raise CliError("invalid_path", "--path 必须是同源相对路径")
    return path


def validate_ttl(value: int) -> int:
    if not 1 <= value <= MAX_TTL:
        raise CliError("invalid_ttl", f"--ttl 必须在 1-{MAX_TTL} 秒之间")
    return value


def cache_root(local_url: str) -> Path:
    digest = hashlib.sha256(local_url.encode("utf-8")).hexdigest()[:24]
    return Path.home() / ".cache" / TOOL_NAME / digest


def state_path(session_dir: Path) -> Path:
    return session_dir / "tunnel-state.json"


def request_path(session_dir: Path) -> Path:
    return session_dir / "request.json"


def log_path(session_dir: Path) -> Path:
    return session_dir / "cloudflared.log"


def ensure_session_dir(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    try:
        session_dir.chmod(0o700)
    except OSError as exc:
        _warn(f"session_dir chmod 0o700 失败：{exc}")


def atomic_json_write(path: Path, data: dict[str, Any], *, mode: int = 0o600) -> None:
    ensure_session_dir(path.parent)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        temp.chmod(mode)
    except OSError as exc:
        _warn(f"状态文件 chmod {oct(mode)} 失败：{exc}")
    temp.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError("invalid_state", f"状态文件无法读取：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise CliError("invalid_state", f"状态文件格式非法：{path}")
    return data


def now_epoch() -> int:
    return int(time.time())


def state_summary(state: dict[str, Any] | None) -> dict[str, Any]:
    # local_url 由 validate_request 唯一提供，state 不再回传，避免合并时盖掉真实目标。
    if not state:
        return {
            "running": False,
            "pid": None,
            "public_url": None,
            "expires_at": None,
        }
    return {
        "running": bool(state.get("running")),
        "pid": state.get("pid"),
        "public_url": state.get("public_url"),
        "expires_at": state.get("expires_at"),
    }


def process_started_at(pid: int) -> str | None:
    # 用 ps 的 lstart 字符串做进程身份校验，同机器格式稳定，跨平台不保证。
    if os.name == "nt":
        return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() or None


def process_matches(state: dict[str, Any]) -> bool:
    # pid + 启动时间戳双重校验，消除子串误判与 pid 复用风险。
    pid = state.get("pid")
    started_at = state.get("process_started_at")
    if not isinstance(pid, int) or pid <= 0 or not isinstance(started_at, str) or not started_at:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return process_started_at(pid) == started_at


def inspect_state(session_dir: Path) -> dict[str, Any]:
    state = read_json(state_path(session_dir))
    if not state:
        return {"state": None, **state_summary(None), "stale": False}
    active = process_matches(state)
    expired = bool(state.get("expires_at") and now_epoch() >= int(state["expires_at"]))
    if active and expired:
        terminate_pid(state["pid"])
        active = False
    if not active:
        state["running"] = False
        state["stopped_at"] = now_epoch()
        atomic_json_write(state_path(session_dir), state)
    return {
        "state": state,
        **state_summary(state),
        "stale": not active and bool(state.get("pid")),
        "expired": expired,
    }


def _curl_request(url: str, *, timeout: int, no_tls_verify: bool) -> tuple[int, bytes]:
    def run(use_doh: bool) -> subprocess.CompletedProcess:
        command = ["curl", "--noproxy", "*", "-sS", "-L", "--max-time", str(timeout)]
        if use_doh:
            command.extend(["--doh-url", "https://1.1.1.1/dns-query"])
        if no_tls_verify:
            command.append("--insecure")
        command.extend(["-A", "port-to-public/1.0", "-w", "\\n%{http_code}", url])
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    result = run(False)
    if result.returncode == 6:
        result = run(True)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise CliError("connection_failed", f"无法连接 {url}：{detail or f'curl exited {result.returncode}'}", retryable=True)
    body, marker, status_text = result.stdout.rpartition(b"\n")
    if not marker:
        raise CliError("connection_failed", f"无法读取 {url} 的 HTTP 状态", retryable=True)
    try:
        return int(status_text), body
    except ValueError as exc:
        raise CliError("connection_failed", f"无法解析 {url} 的 HTTP 状态") from exc


def _python_request(url: str, *, timeout: int, no_tls_verify: bool) -> tuple[int, bytes]:
    context = ssl._create_unverified_context() if no_tls_verify else None
    request = Request(url, headers={"User-Agent": "port-to-public/1.0"})
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return int(response.status), response.read()
    except HTTPError as exc:
        return int(exc.code), exc.read()
    except (URLError, OSError) as exc:
        raise CliError("connection_failed", f"无法连接 {url}：{exc}", retryable=True) from exc


def http_request(url: str, *, timeout: int, no_tls_verify: bool = False) -> tuple[int, bytes]:
    # 本机 loopback 不需要 curl/DoH；公网 Quick Tunnel 使用 curl 的 DoH 回退。
    host = (urlsplit(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return _python_request(url, timeout=timeout, no_tls_verify=no_tls_verify)
    if shutil.which("curl"):
        return _curl_request(url, timeout=timeout, no_tls_verify=no_tls_verify)
    return _python_request(url, timeout=timeout, no_tls_verify=no_tls_verify)


def verify_local(local_url: str, *, no_tls_verify: bool) -> dict[str, Any]:
    status, _ = http_request(local_url, timeout=10, no_tls_verify=no_tls_verify)
    return {"url": local_url, "http_status": status}


def public_url_for_path(public_url: str, public_path: str) -> str:
    return urljoin(public_url.rstrip("/") + "/", public_path.lstrip("/"))


def verify_public_url(
    public_url: str,
    public_path: str,
    *,
    expect: str | None,
    timeout: int,
) -> dict[str, Any]:
    url = public_url_for_path(public_url, public_path)
    started = time.monotonic()
    deadline = started + timeout
    attempts = 0
    last_error: CliError | None = None
    while time.monotonic() < deadline:
        attempts += 1
        try:
            status, body = http_request(url, timeout=min(10, max(1, int(deadline - time.monotonic()))))
        except CliError as exc:
            last_error = exc
            time.sleep(1)
            continue
        elapsed_ms = int((time.monotonic() - started) * 1000)
        expect_matched = expect in body.decode("utf-8", errors="replace") if expect else None
        ok = 200 <= status < 400 and (expect_matched is not False)
        if ok or status < 500:
            return {
                "ok": ok,
                "url": url,
                "http_status": status,
                "expect_matched": expect_matched,
                "latency_ms": elapsed_ms,
                "body_bytes": len(body),
                "attempts": attempts,
            }
        time.sleep(1)
    if last_error:
        raise last_error
    raise CliError("public_verify_timeout", f"公网 URL 在 {timeout} 秒内未就绪：{url}", retryable=True)


def launch_tunnel(
    *,
    session_dir: Path,
    local_url: str,
    ttl: int,
    timeout: int,
    protocol: str,
    no_tls_verify: bool,
) -> dict[str, Any]:
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        raise CliError("cloudflared_missing", "未找到 cloudflared")

    ensure_session_dir(session_dir)
    log_file = log_path(session_dir)
    command = [
        cloudflared,
        "tunnel",
        "--no-autoupdate",
        "--protocol",
        protocol,
        "--url",
        local_url,
    ]
    if no_tls_verify:
        command.append("--no-tls-verify")

    with log_file.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=os.name != "nt",
        )

    started_at_epoch = now_epoch()
    started_lstart = process_started_at(process.pid)
    if not started_lstart:
        terminate_pid(process.pid)
        raise CliError("tunnel_start_failed", "无法读取 cloudflared 进程启动时间，仅支持 macOS/Linux", retryable=False)

    deadline = time.monotonic() + timeout
    public_url = None
    registered = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            detail = log_file.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise CliError("tunnel_start_failed", f"cloudflared 提前退出：{detail}", retryable=True)
        content = log_file.read_text(encoding="utf-8", errors="replace")
        match = URL_PATTERN.search(content)
        if match:
            public_url = match.group(0)
        if "Registered tunnel connection" in content:
            registered = True
        if public_url and registered:
            state = {
                "version": SCHEMA_VERSION,
                "running": True,
                "pid": process.pid,
                "process_started_at": started_lstart,
                "local_url": local_url,
                "public_url": public_url,
                "protocol": protocol,
                "started_at": started_at_epoch,
                "expires_at": started_at_epoch + ttl,
                "ttl": ttl,
                "log_path": str(log_file),
            }
            atomic_json_write(state_path(session_dir), state)
            return state
        time.sleep(0.5)

    terminate_pid(process.pid)
    raise CliError("tunnel_start_timeout", f"等待 Cloudflare Quick Tunnel 超时，查看日志：{log_file}", retryable=True)


def terminate_pid(pid: int) -> bool:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise CliError("stop_denied", f"无权停止 tunnel 进程 {pid}：{exc}") from exc

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.2)

    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return True


def stop_tunnel(session_dir: Path) -> dict[str, Any]:
    state = read_json(state_path(session_dir))
    if not state:
        return {"stopped": False, "already_stopped": True, "reason": "没有该端口的 tunnel 状态"}
    if not process_matches(state):
        state["running"] = False
        state["stopped_at"] = now_epoch()
        atomic_json_write(state_path(session_dir), state)
        return {"stopped": False, "already_stopped": True, "reason": "tunnel 已停止或状态已过期"}

    pid = state["pid"]
    terminate_pid(pid)
    state["running"] = False
    state["stopped_at"] = now_epoch()
    atomic_json_write(state_path(session_dir), state)
    return {"stopped": True, "already_stopped": False, "pid": pid}


