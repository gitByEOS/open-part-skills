"""聚合动作节点产物为稳定 stdout envelope 的 data 部分。"""

from esflow import Node


class RenderResult(Node):
    id = "render_result"
    title = "生成结果信封"

    def accept(self, ctx) -> bool:
        # esflow 已按 action 过滤上游节点，render_result 是终点节点，直接放行。
        return True

    def run(self, ctx) -> dict:
        inspected = ctx.get("inspect_tunnel")
        launched = ctx.get("launch_tunnel")
        verified = ctx.get("verify_public")
        stopped = ctx.get("stop_tunnel")

        state = dict(inspected.get("state") or {})
        if launched:
            state.update(launched)
        if stopped and stopped.get("stopped"):
            state["running"] = False

        action = inspected["action"]
        if action == "start":
            # launched.get("started") 区分新建与复用，避免复用时误报 started。
            status = "started" if launched and launched.get("started") else "running"
        elif action == "status":
            status = "running" if state.get("running") else "stopped"
        elif action == "verify":
            status = "verified"
        else:
            status = "stopped" if stopped and stopped.get("stopped") else "already_stopped"

        skill_root = inspected.get("skill_root", "")
        stop_command = (
            f'python3 "{skill_root}/scripts/run.py" stop --url {inspected["local_url"]}'
            if skill_root
            else ""
        )

        return {
            "action": action,
            "status": status,
            "local_url": inspected["local_url"],
            "public_url": state.get("public_url"),
            "running": bool(state.get("running")),
            "pid": state.get("pid"),
            "expires_at": state.get("expires_at"),
            "verification": verified,
            "stop": stopped,
            "stop_command": stop_command,
        }
