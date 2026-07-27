"""脚本层测试夹具。"""

from __future__ import annotations

from dataclasses import dataclass, field

from clak.commands.types import Script
from clak.runtime.errors import ScriptError
from clak.runtime.output import OutputView
from clak.runtime.params import MissingScriptInputError, ScriptInputs
from clak.runtime.session import Session


class OutputViewProxy:
    """为测试提供稳定、只读的输出查询接口。"""

    def __init__(self, output: OutputView) -> None:
        self._output = output

    @property
    def lines(self) -> tuple[str, ...]:
        return self._output.render_lines()

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def contains(self, text: str) -> bool:
        return text in self.text


@dataclass
class ScriptRun:
    """一次脚本测试运行的结果；可在等待输入时原地续跑。"""

    script: Script
    session: Session
    output: OutputViewProxy
    exit_code: int = 0
    error_text: str = ""
    _exception: Exception | None = field(default=None, repr=False)

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and self._exception is None

    @property
    def failed(self) -> bool:
        return not self.succeeded

    def is_awaiting(self, field_id: str) -> bool:
        request = self.session.pending_request
        return self.session.is_awaiting_input and request is not None and request.field_id == field_id

    def provide(self, field_id: str, value: str) -> None:
        if self.failed:
            return
        try:
            self.session.provide_input(field_id, value)
        except (ScriptError, ValueError, MissingScriptInputError) as error:
            self._set_failure(error)

    def _set_failure(self, error: Exception) -> None:
        self._exception = error
        self.exit_code = 1 if isinstance(error, ScriptError) else 2
        self.error_text = str(error)
        self.session.cancel()


class ScriptTester:
    """按脚本标准生命周期创建并运行一次业务脚本。"""

    def __init__(self, script_cls: type[Script]) -> None:
        self.script_cls = script_cls

    def run(self, inputs: dict[str, str] | None = None) -> ScriptRun:
        script = self.script_cls()
        script_inputs = (
            ScriptInputs(allow_defaults=False)
            if inputs is None
            else ScriptInputs.from_pairs(inputs, allow_defaults=False)
        )
        session = Session(script.output, inputs=script_inputs)
        run = ScriptRun(script, session, OutputViewProxy(script.output))
        session.on_exit(script.on_exit)
        try:
            script.on_enter(session)
            script.run()
        except (ScriptError, ValueError, MissingScriptInputError) as error:
            run._set_failure(error)
        return run
