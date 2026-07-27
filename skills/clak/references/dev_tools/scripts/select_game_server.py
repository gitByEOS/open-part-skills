from __future__ import annotations

from clak import AskAnswer, AskChoice, AskMode, AskRequest, Script, Session

from ..context import context


class SelectGameServerScript(Script):
    name = "/select-game-server"
    description = "选择游戏后端服务器"

    def run(self) -> None:
        def ask_game_server() -> int:
            def save(answer: AskAnswer) -> None:
                context.game_server = answer.primary
                self.output.push(f"当前后端服已切换为：{context.game_server}")

            return self.ask_tool(
                AskRequest(
                    field_id="game_server",
                    prompt="选择游戏后端服",
                    default=context.game_server,
                    choices=(
                        AskChoice(label="开发 game-dev", value="game-dev"),
                        AskChoice(label="预发 game-staging", value="game-staging"),
                        AskChoice(label="生产 game-prod", value="game-prod"),
                    ),
                    mode=AskMode.FILTER,
                ),
                save,
            )

        self.add_step(True, ask_game_server, "ask_game_server")
        self.run_steps()
