from __future__ import annotations

import subprocess
import sys

from clak import AskAnswer, AskChoice, AskRequest, Script, ScriptError, Session


class VerifyReleaseScript(Script):
    """用可控的子进程展示成功、失败退出码及错误输出。"""

    name = "/verify-release"
    description = "运行发布检查（可选择模拟失败）"

    def run(self) -> None:
        outcome = "success"

        def ask_outcome() -> int:
            def save(answer: AskAnswer) -> None:
                nonlocal outcome
                outcome = answer.primary
                self.output.push(f"检查模式：{outcome}")

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
                save,
            )

        def run_check() -> int:
            command = (
                "import sys; "
                "print('发布检查通过') if sys.argv[1] == 'success' "
                "else print('发现不兼容资源', file=sys.stderr); "
                "raise SystemExit(0 if sys.argv[1] == 'success' else 1)"
            )
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", command, outcome],
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

        self.add_step(True, ask_outcome, "ask_outcome")
        self.add_step(True, run_check, "run_check")
        self.run_steps()
