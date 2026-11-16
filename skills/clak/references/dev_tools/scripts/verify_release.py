from __future__ import annotations

import subprocess
import sys
from time import sleep

from clak import AskAnswer, AskChoice, AskRequest, Script, ScriptError, Session

from ..context import context


RELEASE_CHECKS = (
    "检查发布配置",
    "检查资源清单",
    "检查资源版本",
    "检查服务连接",
    "检查接口契约",
    "检查发布就绪状态",
)


class VerifyReleaseScript(Script):
    """业务只定义检查步骤，进度由会话统一管理。"""

    name = "/verify-release"
    description = "发布检查"

    def __init__(self) -> None:
        super().__init__()
        self._outcome = "success"

    def on_enter(self, session: Session) -> None:
        super().on_enter(session)
        self.output.push("本地模拟，不连接或修改真实服务器")
        self.output.push(f"资源服：{context.res_server} · 后端服：{context.game_server}")

    def on_exit(self) -> None:
        self.output.push("发布检查会话已结束")
        super().on_exit()

    def run(self) -> None:
        self.add_step(True, self._ask_outcome, "选择检查结果")
        for name in RELEASE_CHECKS:
            self.add_step(True, self._check, name)
        self.add_step(True, self._verify, "验证发布结果")
        self.run_steps()

    def _ask_outcome(self) -> int:
        return self.ask_tool(
            AskRequest(
                field_id="outcome",
                prompt="选择发布检查结果",
                default="success",
                choices=(
                    AskChoice(label="成功", value="success"),
                    AskChoice(label="模拟失败", value="failure"),
                ),
            ),
            self._save_outcome,
        )

    def _save_outcome(self, answer: AskAnswer) -> None:
        self._outcome = answer.primary

    def _check(self) -> int:
        sleep(0.6)
        return 0

    def _verify(self) -> int:
        command = (
            "import sys; "
            "print('发布检查通过') if sys.argv[1] == 'success' "
            "else print('发现不兼容资源', file=sys.stderr); "
            "raise SystemExit(0 if sys.argv[1] == 'success' else 1)"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", command, self._outcome],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ScriptError(f"无法启动发布检查：{error}") from error
        if completed.stdout.strip():
            self.output.push(completed.stdout.strip())
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"退出码 {completed.returncode}"
            raise ScriptError(f"发布检查失败：{detail}", exit_code=1)
        return 0
