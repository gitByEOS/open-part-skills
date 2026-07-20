"""停止本会话创建的 Cloudflare Quick Tunnel。"""

from pathlib import Path

from esflow import Node

from common import stop_tunnel


class StopTunnel(Node):
    id = "stop_tunnel"
    title = "停止 Cloudflare Quick Tunnel"

    def accept(self, ctx) -> bool:
        return ctx.get("inspect_tunnel")["action"] == "stop"

    def run(self, ctx) -> dict:
        inspected = ctx.get("inspect_tunnel")
        return stop_tunnel(Path(inspected["session_dir"]))
