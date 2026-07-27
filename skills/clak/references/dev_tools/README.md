# dev_tools 示例

这是一个可直接运行、也适合复制进业务仓库的 clak 项目。它使用自己的 `Clak` 实例注册业务脚本，同一个入口同时支持 TUI 和无头执行。

## 复制到独立业务项目后运行

这是新项目的推荐路径：将本目录复制为业务仓库中的 `dev_tools/` 包，并在其父目录执行。无需取得或安装 `esclak` 源码仓库。

```bash
python -m pip install esclak pytest
python -m dev_tools
python -m dev_tools exec /pack-upload \
  --set version=1.2.3 \
  --set targets=base,win
python -m pytest
```

`pytest` 只用于运行本项目的测试；部署时不需要测试可只安装 `esclak`。

不要使用全局 `clak exec /pack-upload`：全局命令不知道业务项目注册了哪些脚本。`python -m dev_tools` 才会加载本目录的 `app`。

无头执行中，不带任何 `--set` 时会采用非空 `AskRequest.default`；一旦提供了任意 `--set`，其余字段只有在附加 `--use-defaults` 时才会采用默认值。未提供且没有可用默认值的字段退出码为 `2`。`--set` 的值始终优先于默认值。

在 TUI 主输入区直接键入字母即可搜索命令，不需要先输入 `/`。搜索采用子序列模糊匹配，例如 `pu` 可匹配 `/pack-upload`；`Enter` 执行选中项，`Tab` 补全为完整命令。

## 脚本一览

- `/pack-upload`：询问版本和目标，运行子进程生成临时产物，按条件校验 Windows 清单，上传后清理临时目录。
- `/select-res-server`：过滤选择资源服，完成后 `/status` 立即更新。
- `/select-game-server`：过滤选择后端服，完成后 footer 立即更新。
- `/verify-release`：运行可控子进程，演示成功及退出码为 1 的业务失败。

可以直接验证失败路径：

```bash
python -m dev_tools exec /verify-release --set outcome=failure
echo $?
# 1
```

候选值会严格校验，下面的命令返回退出码 2，不会修改当前服务器：

```bash
python -m dev_tools exec /select-res-server \
  --set res_server=unknown
```

## 目录

```text
dev_tools/
├── README.md
├── __init__.py
├── __main__.py       # app.run_cli()：项目级 tui/exec 入口
├── app.py            # 创建 app，注册所有脚本
├── context.py        # 多脚本共享的进程内状态
└── scripts/
    ├── pack_upload.py
    ├── select_game_server.py
    ├── select_res_server.py
    └── verify_release.py
```

`context.py` 定义模块级 `context`：资源服选择脚本写入 `res_server`，后端服选择脚本写入 `game_server`；上传脚本、状态栏和 footer 读取这些值。它只在当前 Python 进程内共享；关闭并重新启动应用后会恢复默认值。`reset()` 用于测试隔离，跨进程持久化应接入配置文件或数据库。

## 编写脚本时必须理解的约定

1. `app.register(MyScript)` 注册的是脚本类，每次执行都会创建新实例。
2. `self.add_step(can_do, task, name)` 向本次执行队列追加一步，`can_do` 可以是布尔值或运行时判断函数。
3. `self.run_steps()` 绑定完成回调并启动执行队列，负责在全部步骤结束时触发生命周期清理。
4. 任务返回 `0` 表示同步继续；非零表示队列挂起，不是失败退出码。
5. 需要用户输入时返回 `self.ask_tool(AskRequest(...), on_answer)`，框架会在得到答案后恢复下一项。
6. `AskRequest.default` 是必填构造参数；空字符串不会被无头 CLI 自动采用。
7. 业务失败抛出 `ScriptError`；输入格式错误抛出 `ValueError`。
8. 临时文件、子进程等资源在 `on_exit()` 清理，完成、失败和用户中断都会调用它。

候选、多选和过滤字段由框架统一校验。只有包含 `AskChoice(value=None)` 的单选问题允许用户输入候选之外的自定义文本，业务格式仍应在答案回调中校验。

每个脚本的 `self.output.push()` 默认以 `[脚本名] ` 标记每行输出，例如 `[pack-upload] 上传完成`，便于在 history 中区分多个脚本。

## 测试

仓库根目录的测试覆盖 TUI、无头参数、非法 choice、子进程失败和资源清理：

```bash
python -m pytest
```

## 维护者附录：从 esclak 源码仓库运行

仅在维护 `esclak` 本身时，在其源码仓库根目录执行以下命令以使用当前未发布源码：

```bash
python3 -m pip install -e ".[dev]"
python3 -m examples.dev_tools
python3 -m examples.dev_tools tui
python3 -m examples.dev_tools exec /pack-upload --use-defaults
```

这不是复制本参考实现到独立项目时的前置条件。
