"""验证当前会话的公网 HTTP 链路。"""

from esflow import Node

from common import CliError, verify_public_url


class VerifyPublic(Node):
    id = "verify_public"
    title = "验证公网 HTTP 链路"

    def accept(self, ctx) -> bool:
        return ctx.get("inspect_tunnel")["action"] in {"start", "verify"}

    def run(self, ctx) -> dict:
        inspected = ctx.get("inspect_tunnel")
        launched = ctx.get("launch_tunnel")
        public_url = None
        if launched:
            public_url = launched.get("public_url")
        if not public_url:
            public_url = inspected.get("public_url")
        if not public_url:
            raise CliError("tunnel_not_running", "该端口没有可验证的运行中 tunnel")
        return verify_public_url(
            public_url,
            inspected["path"],
            expect=inspected["expect"],
            timeout=inspected["verify_timeout"],
        )

    def deliver(self, artifact) -> bool:
        return bool(artifact and artifact.get("ok"))
