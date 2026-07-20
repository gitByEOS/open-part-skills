"""启动或复用 Cloudflare Quick Tunnel。"""

from pathlib import Path

from esflow import Node

from common import launch_tunnel


class LaunchTunnel(Node):
    id = "launch_tunnel"
    title = "启动 Cloudflare Quick Tunnel"

    def accept(self, ctx) -> bool:
        return ctx.get("inspect_tunnel")["action"] == "start"

    def run(self, ctx) -> dict:
        inspected = ctx.get("inspect_tunnel")
        if inspected["running"]:
            return {"started": False, **(inspected.get("state") or {})}
        state = launch_tunnel(
            session_dir=Path(inspected["session_dir"]),
            local_url=inspected["local_url"],
            ttl=inspected["ttl"],
            timeout=inspected["timeout"],
            protocol=inspected["protocol"],
            no_tls_verify=inspected["no_tls_verify"],
        )
        return {"started": True, **state}
