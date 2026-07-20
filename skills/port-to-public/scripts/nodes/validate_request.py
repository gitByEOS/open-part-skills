"""解析 CLI 入参并准备内部 session。"""

from __future__ import annotations

import time

from esflow import Node

from common import (
    CliError,
    DEFAULT_TIMEOUT,
    DEFAULT_TTL,
    DEFAULT_VERIFY_TIMEOUT,
    VALID_ACTIONS,
    atomic_json_write,
    cache_root,
    ensure_session_dir,
    normalize_public_path,
    normalize_target,
    request_path,
    validate_ttl,
    verify_local,
)


class ValidateRequest(Node):
    id = "validate_request"
    title = "校验公网暴露请求"

    def run(self, ctx) -> dict:
        action = self.kwargs.get("action")
        if action not in VALID_ACTIONS:
            raise CliError("invalid_action", f"未知动作：{action}")

        local_url = normalize_target(self.kwargs.get("port"), self.kwargs.get("url"))
        session_dir = cache_root(local_url)
        ensure_session_dir(session_dir)
        ttl = validate_ttl(int(self.kwargs.get("ttl", DEFAULT_TTL)))
        path = normalize_public_path(self.kwargs.get("path"))
        timeout = int(self.kwargs.get("timeout", DEFAULT_TIMEOUT))
        verify_timeout = int(self.kwargs.get("verify_timeout", DEFAULT_VERIFY_TIMEOUT))
        if timeout < 1 or verify_timeout < 1:
            raise CliError("invalid_timeout", "超时必须为正整数")

        if action == "start":
            if not self.kwargs.get("confirm_public"):
                raise CliError(
                    "public_confirmation_required",
                    "启动前必须显式传入 --confirm-public；该 URL 无认证，持有者均可访问",
                )
            local_probe = verify_local(local_url, no_tls_verify=bool(self.kwargs.get("no_tls_verify")))
            atomic_json_write(
                request_path(session_dir),
                {
                    "local_url": local_url,
                    "created_at": time.time_ns(),
                    "ttl": ttl,
                    "protocol": self.kwargs.get("protocol", "http2"),
                },
            )
        else:
            local_probe = None

        return {
            "action": action,
            "local_url": local_url,
            "session_dir": str(session_dir),
            "ttl": ttl,
            "timeout": timeout,
            "verify_timeout": verify_timeout,
            "path": path,
            "expect": self.kwargs.get("expect"),
            "protocol": self.kwargs.get("protocol", "http2"),
            "no_tls_verify": bool(self.kwargs.get("no_tls_verify")),
            "local_probe": local_probe,
            "skill_root": self.kwargs.get("skill_root", ""),
        }
