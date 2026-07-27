from __future__ import annotations

from clak import Clak, FooterViewData

from .context import context
from .scripts.pack_upload import PackUploadScript
from .scripts.select_game_server import SelectGameServerScript
from .scripts.select_res_server import SelectResServerScript
from .scripts.verify_release import VerifyReleaseScript


def status() -> str:
    return f"当前资源服：{context.res_server}"


def footer(footer_data: FooterViewData) -> str:
    return f"{footer_data.hint} · 当前后端服：{context.game_server}"


app = Clak(status=status, footer_view=footer)
app.register(
    PackUploadScript,
    SelectResServerScript,
    SelectGameServerScript,
    VerifyReleaseScript,
)
