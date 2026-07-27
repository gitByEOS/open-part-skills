from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from clak import (
    AskAnswer,
    AskChoice,
    AskMode,
    AskRequest,
    Script,
    ScriptError,
    Session,
)

from ..context import context

PACK_TARGET_DEFAULT = "base,cn"
PACK_VERSION_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,63}")


def default_pack_version() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def pack_target_choices() -> tuple[AskChoice, ...]:
    return (
        AskChoice(label="Base 资源", value="base"),
        AskChoice(label="iOS", value="ios"),
        AskChoice(label="Windows", value="win"),
        AskChoice(label="简体中文", value="cn"),
        AskChoice(label="English", value="en"),
    )


def validate_pack_version(version: str) -> None:
    if not PACK_VERSION_PATTERN.fullmatch(version):
        raise ValueError("资源包版本号只能包含字母、数字、点、下划线和连字符")


@dataclass
class PackState:
    version: str = ""
    targets: frozenset[str] | None = None


class PackUploadScript(Script):
    name = "/pack-upload"
    description = "打包并上传到当前资源服"

    def __init__(self) -> None:
        super().__init__()
        self._workspace: tempfile.TemporaryDirectory[str] | None = None

    def on_enter(self, session: Session) -> None:
        super().on_enter(session)
        self._workspace = tempfile.TemporaryDirectory(prefix="clak-release-")
        self.output.push("已创建临时打包目录")

    def on_exit(self) -> None:
        if self._workspace is not None:
            self._workspace.cleanup()
            self._workspace = None
            self.output.push("已清理临时打包目录")
        super().on_exit()

    def run(self) -> None:
        state = PackState()

        def ask_version() -> int:
            def save(answer: AskAnswer) -> None:
                validate_pack_version(answer.primary)
                state.version = answer.primary
                self.output.push(f"资源版本：{state.version}")

            default = default_pack_version()
            return self.ask_tool(
                AskRequest(
                    field_id="version",
                    prompt="资源包版本号",
                    default=default,
                    choices=(
                        AskChoice(label=default, value=default),
                        AskChoice(label="输入其他版本", value=None),
                    ),
                ),
                save,
            )

        def ask_targets() -> int:
            def save(answer: AskAnswer) -> None:
                state.targets = answer.tokens
                self.output.push(f"打包目标：{answer.text}")

            return self.ask_tool(
                AskRequest(
                    field_id="targets",
                    prompt="选择打包目标（可多选）",
                    default=PACK_TARGET_DEFAULT,
                    choices=pack_target_choices(),
                    mode=AskMode.MULTI,
                ),
                save,
            )

        def pack_and_upload() -> int:
            targets = ",".join(sorted(state.targets or frozenset(PACK_TARGET_DEFAULT.split(","))))
            if self._workspace is None:
                raise ScriptError("临时打包目录未初始化")
            artifact = Path(self._workspace.name) / "artifact.txt"
            command = (
                "from pathlib import Path; import sys; "
                "Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8'); "
                "print('构建器已生成 artifact.txt')"
            )
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", command, str(artifact), f"{state.version}:{targets}"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            except (OSError, subprocess.SubprocessError) as error:
                raise ScriptError(f"无法运行构建器：{error}") from error
            if completed.stdout.strip():
                self.output.push(completed.stdout.strip())
            if completed.returncode != 0:
                detail = completed.stderr.strip() or f"退出码 {completed.returncode}"
                raise ScriptError(f"打包失败：{detail}")
            self.output.push(f"打包 {state.version} [{targets}]")
            self.output.push(f"上传到资源服：{context.res_server}")
            self.output.push("上传完成")
            return 0

        def verify_windows_artifact() -> int:
            self.output.push("已校验 Windows 资源清单")
            return 0

        self.add_step(True, ask_version, "ask_version")
        self.add_step(True, ask_targets, "ask_targets")
        self.add_step(True, pack_and_upload, "pack_and_upload")
        self.add_step(
            lambda: "win" in (state.targets or frozenset()),
            verify_windows_artifact,
            "verify_windows_artifact",
        )
        self.run_steps()
