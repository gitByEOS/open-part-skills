---
name: tmux-serv
description: 使用全局 ~/.tmux.services 管理多个项目的常驻服务。支持注册、启动、精确重启、停止、查看状态与日志
version: 1.0.0
dependencies:
  - tmux
repository: https://github.com/gitByEOS/open-part-skills
---

# tmux-serv

用一个可执行的 `~/.tmux.services` 管理多项目服务；每个项目只维护自己的前台 launcher。

```text
~/.tmux.services                         # 全局清单与 tmux 生命周期
~/dev/project-a/tools/start_ocr_server.sh
~/dev/project-b/tools/start_chat_server.sh
```

服务名全局唯一时直接用 `<name>`，session 为 `serv-<name>`；只有重名时才用 `<project>/<name>`，session 为 `serv-<project>-<name>`。

## 依赖

需要 Bash 3.2+ 与 tmux：

```bash
brew install tmux       # macOS
# apt install tmux      # Debian / Ubuntu
```

## 安装全局脚本

先将本 skill 的绝对目录记为 `SKILL_ROOT`：

```bash
SKILL_ROOT="<tmux-serv skill 的绝对路径>"
bash "$SKILL_ROOT/scripts/install.sh"
```

首次安装写入 `~/.tmux.services` 并设为 `0700`。**目标已存在时安装器拒绝覆盖**。

隔离/测试场景可指定自定义目标路径，不写入 `~/.tmux.services`，目标已存在时同样拒绝覆盖：

```bash
bash "$SKILL_ROOT/scripts/install.sh" --target /path/to/.tmux.services
```

升级模板：

```bash
bash "$SKILL_ROOT/scripts/install.sh" --upgrade
```

升级只保留以下标记之间的用户服务区，用新版替换其余引擎，且先创建带时间戳的 `.bak` 备份：

```text
# >>> tmux-serv user services >>>
# <<< tmux-serv user services <<<
```

如果标记缺失、重复，或合并结果校验失败，安装器拒绝修改。安装器只清理自身临时合并文件，不删除用户配置或备份。不要手工改标记之外的引擎；复杂定制应保留自己的 fork。

## 项目 launcher 契约

每个服务一个项目内脚本，直接放在项目根的 `tools/` 下：

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

exec env PORT="${API_PORT:-3000}" node server.js
```

Python 服务示例：

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# 优先用项目内 venv，没有则回落到系统 python
if [[ -x ".venv/bin/python" ]]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

exec env \
    PORT="${API_PORT:-8000}" \
    HOST="${API_HOST:-127.0.0.1}" \
    "$PY" -m app.main
```

若是 uv 管理的项目，可简化为：

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
exec env PORT="${API_PORT:-8000}" uv run python -m app.main
```

必须满足：

1. 文件位于 `<project>/tools/`，存在且可执行
2. 从自身路径定位项目，不依赖调用者 cwd
3. 不创建 tmux，不使用 `nohup`、尾随 `&` 或自身 daemonize
4. 最终 `exec` 前台主进程；依赖、端口、参数与环境默认值归项目维护
5. 启动失败写 stderr 并返回非零；脚本应能从任意 cwd 直接执行
6. 密钥不要写入 `~/.tmux.services`；由项目的安全配置或进程环境提供



## 注册服务

只编辑 `~/.tmux.services` 的用户服务区：

```bash
configure_services() {
    start_service "project-a" "ocr" \
        "$HOME/dev/project-a/tools/start_ocr_server.sh"

    start_service "project-b" "chat-room" \
        "$HOME/dev/project-b/tools/start_chat_server.sh"
}
```

`start_service` 恰好接收三个参数：


| 参数         | 规则                                   |
| ---------- | ------------------------------------ |
| `project`  | 1–40 位小写字母、数字、单连字符；禁止首尾连字符与 `--`     |
| `service`  | 同上；只需在项目内唯一                          |
| `launcher` | 绝对路径或 `~/` 路径；允许空格，必须直接位于项目 `tools/` |


`project/service` 复合键必须唯一。若 `service` 在全表唯一，CLI 直接用 `service`，session 为 `serv-<name>`；若重名，则必须用 `project/service`，session 为 `serv-<project>-<name>`。新增第二个同名服务会改变原服务的派生 session，旧 `serv-<name>` 不会被自动停止；应先确认归属并精确停止，再逐项启动新 session。注册表是可执行 Shell，只能安装和编辑自己信任的内容；包括 `--check`、`--status` 在内的调用都会执行配置区来加载条目，但只有启动或重启才执行 launcher。

注册后先校验，不启动服务：

```bash
~/.tmux.services --check
```



## 日常操作

```bash
# 仅补启动全部缺失服务；已有 session 不动
~/.tmux.services

# service 唯一时直接使用短名
~/.tmux.services chat-room
~/.tmux.services --restart chat-room

# 只有重名时才带项目名
~/.tmux.services project-a/api
~/.tmux.services --restart project-a/api

# 明确要求时才重启全部；非事务操作，失败不会回滚前项
~/.tmux.services --restart-all

# 查看全部或单项状态
~/.tmux.services --status
~/.tmux.services --status chat-room

# 最近 200 行、附着、精确停止
~/.tmux.services --logs chat-room
~/.tmux.services --attach chat-room
~/.tmux.services --stop chat-room
```

所有存在性检查、停止和操作目标都使用 tmux 的 `=<session>` 精确匹配。启动后的 1 秒稳定窗口内若 session 消失，命令返回 `70` 并提示直接运行 launcher 排查；这不是端口或 HTTP 健康检查。

## 安全默认值

- 无参数只补启动缺失服务，不重启已有服务
- 只有显式 `--restart-all` 才全量重启
- 不 `source` 外部配置，不 `eval` 服务命令；总脚本直接执行已注册 launcher
- launcher 路径会物理规范化，拒绝符号链接、相对路径与 `tools/` 外入口
- `--status` 只列注册服务，不扫描或操作其他 `serv-` session
- 测试专用 `TMUX_SERV_SOCKET_NAME` 可切换独立 tmux server；日常不要设置。该变量需在调用 `~/.tmux.services` 前 `export`，写入配置文件无效；所有 `tmux` 验收命令必须带 `-L "$TMUX_SERV_SOCKET_NAME"` 才能命中隔离 server



## 退出码


| 退出码  | 含义                     |
| ---- | ---------------------- |
| `0`  | 操作完成，含“已运行/未运行所以跳过”    |
| `64` | 参数、名称或注册配置错误           |
| `66` | launcher 缺失、不可执行或路径不合规 |
| `69` | tmux 缺失，或日志/附着目标未运行    |
| `70` | tmux 启停失败，或服务启动后立即退出   |


`--restart-all` 逐项执行且不是事务；前项成功、后项失败时不会回滚。

## 验收

```bash
bash -n ~/.tmux.services
~/.tmux.services --check
~/.tmux.services <name>
tmux has-session -t '=serv-<name>'
tmux display-message -p -t '=serv-<name>:' '#{pane_current_path}'
~/.tmux.services --status <name>

# 仅重名服务改用 project/service 与 serv-<project>-<name>
~/.tmux.services <project>/<name>
tmux has-session -t '=serv-<project>-<name>'
```



## 隔离测试

测试专用，日常无需设置

```bash
export TMUX_SERV_SOCKET_NAME=tmuxserv-sandbox
~/.tmux.services <name>
tmux -L "$TMUX_SERV_SOCKET_NAME" has-session -t '=serv-<name>'
tmux -L "$TMUX_SERV_SOCKET_NAME" display-message -p -t '=serv-<name>:' '#{pane_current_path}'
~/.tmux.services --status <name>
unset TMUX_SERV_SOCKET_NAME
```

再按服务协议检查端口、健康接口和日志。