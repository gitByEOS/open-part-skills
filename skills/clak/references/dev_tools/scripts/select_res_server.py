from __future__ import annotations

from clak import AskAnswer, AskChoice, AskMode, AskRequest, Script, Session

from ..context import context


class SelectResServerScript(Script):
    name = "/select-res-server"
    description = "选择资源服务器"

    def run(self) -> None:
        def ask_res_server() -> int:
            def save(answer: AskAnswer) -> None:
                context.res_server = answer.primary
                self.output.push(f"当前资源服已切换为：{context.res_server}")

            return self.ask_tool(
                AskRequest(
                    field_id="res_server",
                    prompt="选择资源服",
                    default=context.res_server,
                    choices=(
                        AskChoice(label="开发 res-dev", value="res-dev"),
                        AskChoice(label="预发 res-staging", value="res-staging"),
                        AskChoice(label="生产 res-prod", value="res-prod"),
                    ),
                    mode=AskMode.FILTER,
                ),
                save,
            )

        self.add_step(True, ask_res_server, "ask_res_server")
        self.run_steps()
