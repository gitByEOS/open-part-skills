from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DevContext:
    res_server: str = "res-dev"
    game_server: str = "game-dev"

    def reset(self) -> None:
        self.res_server = "res-dev"
        self.game_server = "game-dev"


context = DevContext()
