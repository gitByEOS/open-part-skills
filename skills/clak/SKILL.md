---
name: clak
description: 使用 clak 创建、修改、调试和测试固定流程业务脚本，适用于编排步骤、收集交互输入、提供 TUI 与无头 CLI 或测试业务脚本的场景
version: 1.0.0
dependencies:
  - python3
  - esclak
  - pytest
repository: https://github.com/gitByEOS/esclak
---

# clak 业务脚本开发

使用 `clak` 构建固定流程业务工具。业务代码创建自己的 `Clak` 实例并注册 `Script` 子类；全局 `clak` 命令只包含内置命令，不能运行业务脚本。

## 安装方式

运行及测试本 skill 的示例均需要以下依赖：

```bash
python -m pip install esclak pytest
```

生产项目若不运行 pytest，可以只安装 `esclak`；但本文“测试”和“提交前检查”章节的命令要求安装 `pytest`。

## Skill 内置参考实现

此 skill 自包含可复制的参考代码。按需求读取相对于本文件的路径：

- `references/dev_tools/README.md`：完整用法和运行命令
- `references/dev_tools/app.py`：应用、状态栏和 footer 注册
- `references/dev_tools/__main__.py`：项目级 CLI 入口
- `references/dev_tools/scripts/select_res_server.py`：过滤选择和共享状态
- `references/dev_tools/scripts/pack_upload.py`：多步编排、子进程、条件步骤和资源清理
- `references/dev_tools/scripts/verify_release.py`：业务失败与退出码
- `references/testing.py`：`ScriptTester` 与 `ScriptRun` 测试夹具

不要将参考项目作为依赖导入。复制其结构和模式到业务项目；目标项目只需安装 `esclak` 包即可使用本 skill。

## 最小项目结构

```text
my_tools/
├── __init__.py
├── __main__.py
├── app.py
└── scripts/
    ├── __init__.py
    └── deploy.py
```

```python
# app.py
from clak import Clak
from .scripts.deploy import DeployScript

app = Clak(status="发布工具 · staging")
app.register(DeployScript)
```

```python
# __main__.py
from .app import app

app.run_cli(prog="my-tools")
```

业务入口必须是：

```bash
python -m my_tools
python -m my_tools exec /deploy
```

不要执行 `clak exec /deploy`，它不会加载业务项目注册的脚本。

## Script 约定

脚本每次运行会创建新实例。`run` 无参数；框架在 `on_enter(session)` 中绑定会话，再在结束、失败或取消时调用 `on_exit()`。

```python
from clak import Script


class DeployScript(Script):
    name = "/deploy"
    description = "发布服务"

    def run(self) -> None:
        def deploy() -> int:
            self.output.push("发布完成")
            return 0

        self.add_step(True, deploy, "deploy")
        self.run_steps()
```

- `name` 必须是 slash 命令，如 `/deploy`
- `run(self)` 内定义并编排本次执行的步骤
- `self.add_step(can_do, task, name)` 添加步骤，`can_do` 为布尔值或无参判断函数
- 步骤返回 `0` 继续，非 `0` 表示等待输入后恢复，不是业务失败
- 以 `self.run_steps()` 结束 `run`，不要直接操作 `Session` 的执行队列
- `self.output.push()` 自动加 `[script-name] ` 前缀
- 预期业务失败抛 `ScriptError(message, exit_code=1)`；参数格式不合法抛 `ValueError`

## 收集输入

输入步骤返回 `self.ask_tool(request, on_answer)`，答案回调保存业务状态；下一步骤会在输入提交后继续。

```python
from clak import AskAnswer, AskChoice, AskMode, AskRequest


def ask_environment() -> int:
    def save(answer: AskAnswer) -> None:
        state.environment = answer.primary
        self.output.push(f"环境：{state.environment}")

    return self.ask_tool(
        AskRequest(
            field_id="environment",
            prompt="选择环境",
            default="staging",
            choices=(
                AskChoice(label="预发", value="staging"),
                AskChoice(label="生产", value="production"),
            ),
            mode=AskMode.SINGLE,
        ),
        save,
    )
```

`AskRequest.default` 是 `esclak` 当前 API 的**必填构造参数**，即使业务不希望提供可用默认值也必须显式传入，例如 `default=""`。只有非空默认值才能被无头 CLI 自动采用；空默认值与缺失输入一样会失败。

无头 CLI 的真实输入规则如下：

| 命令形态 | 未提供的 ask 字段行为 |
|---|---|
| 不带任何 `--set`，如 `python -m my_tools exec /deploy` | 自动采用每个字段的非空 `AskRequest.default`。没有可用默认值时退出码为 `2`。 |
| 带 `--set environment=staging` | 该字段采用显式值。若还有未提供字段，默认值**不会**自动采用；缺失字段退出码为 `2`。 |
| 带 `--set ... --use-defaults` | 显式 `--set` 优先；其余字段采用各自的非空默认值。 |

因此，设计无头批处理时应为安全的默认路径声明默认值；对必须由调用者确认的字段传 `default=""`，并用 `--set` 提供它。`--use-defaults` 不是“跳过校验”：框架仍会校验 choice，答案回调仍应校验业务格式。

- `field_id` 是无头模式的 `--set field_id=value` 键
- `AskMode.SINGLE` 单选，`MULTI` 多选，`FILTER` 可过滤选择
- 仅 `AskChoice(value=None)` 允许单选字段输入候选外文本，回调仍须校验业务格式
- 无头运行：`python -m my_tools exec /deploy --set environment=staging`

## 资源、状态与错误边界

- 临时目录、文件句柄和外部资源在 `on_enter` 创建，在 `on_exit` 清理；清理必须覆盖完成、失败和取消
- 跨脚本的进程内状态放入显式 `context.py`，并提供 `reset()` 供测试隔离
- 调外部命令使用 `subprocess.run(..., check=False, timeout=...)`，将启动异常和非零退出码转换成 `ScriptError`
- 路径、用户输入和权限参数先校验；不要把失败退出码误写成步骤挂起

## 测试

优先用 `ScriptTester` 验证脚本生命周期、等待输入、成功和失败路径。

```python
from clak import ScriptTester
from my_tools.scripts.deploy import DeployScript


def test_deploy_asks_then_completes():
    run = ScriptTester(DeployScript).run()
    assert run.is_awaiting("environment")

    run.provide("environment", "staging")

    assert run.succeeded
    assert run.output.contains("发布完成")
```

每个脚本至少覆盖：

1. 默认或完整输入的成功路径
2. 每个必填输入缺失时的行为
3. 非法候选或格式错误返回退出码 `2`
4. `ScriptError` 业务失败返回预期退出码
5. 有资源时，完成、失败、取消均执行清理
6. 条件步骤的执行与跳过

最后运行：

```bash
python -m pytest
python -m my_tools exec /deploy --set environment=staging
```

## 提交前检查

- 业务入口而非全局 `clak` 命令可运行
- `run(self)` 已调用一次 `self.run_steps()`
- 输出具备可定位的业务信息
- 无头成功、业务失败、参数失败的退出码分别正确
- TUI 手测搜索、输入、取消以及动态状态或 footer
