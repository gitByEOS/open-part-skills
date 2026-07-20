"""port-to-public 的动作型 esflow DAG。"""

from esflow import edge, flow


@flow(id="port-to-public", title="本机端口临时公网暴露")
class PortToPublicFlow:
    nodes = [
        "validate_request",
        "inspect_tunnel",
        "launch_tunnel",
        "verify_public",
        "stop_tunnel",
        "render_result",
    ]
    edges = [
        edge("validate_request", "inspect_tunnel"),
        edge("inspect_tunnel", "launch_tunnel"),
        edge("inspect_tunnel", "verify_public"),
        edge("inspect_tunnel", "stop_tunnel"),
        edge("launch_tunnel", "verify_public"),
        edge("inspect_tunnel", "render_result"),
        edge("launch_tunnel", "render_result"),
        edge("verify_public", "render_result"),
        edge("stop_tunnel", "render_result"),
    ]
