"""读取并核验本 skill 创建的 tunnel 状态。"""

from pathlib import Path

from esflow import Node

from common import inspect_state


class InspectTunnel(Node):
    id = "inspect_tunnel"
    title = "检查 tunnel 会话"

    def run(self, ctx) -> dict:
        request = ctx.get("validate_request")
        inspected = inspect_state(Path(request["session_dir"]))
        return {**request, **inspected}
