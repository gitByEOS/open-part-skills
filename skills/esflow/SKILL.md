---
name: esflow
description: >-
  用 esflow 框架编排 Python DAG workflow：先把需求描述拆成输入、产物、节点、边、人机/Agent 协作点，再声明 DAG 并跑通流程。使用场景：用户提到 esflow、要写 flow / Node / Runner / checkpoint / FanOut / pass_check，或在 Python 项目里要把多步骤任务串成 DAG、需要单步调试 / 暂停确认 / agent 介入 / 复用上游产物续跑时使用。
version: 0.1.4
dependencies:
  - "python>=3.10"
  - esflow
repository: https://github.com/gitByEOS/esflow
---

# esflow

esflow 是轻量 Python DAG workflow 框架。用目录约定声明节点，`@flow` + `edge()` 组织 DAG，`Runner.run()` 输出事件流，支持并行副本、暂停协作、定点续跑、扇出和兜底链。

完整用法见 `[reference.md](reference.md)`。本文件只保留使用时必须先想清楚的要点。

## 需求建模

不要直接写 Node。先把用户需求压成一张最小 DAG 设计：

1. **输入**：用户必须提供什么，哪些可以给默认值，哪些需要 `pass_check`
2. **产物**：最终输出文件是什么，stdout envelope 要暴露哪些路径或字段
3. **节点**：每个节点只做一件事，命名用业务动作，不用 `step1` / `process`
4. **边**：只表达真实数据依赖；没有依赖的任务让 DAG 同轮并行
5. **暂停点**：人工确认用 `TO_HUMAN`，Agent 写产物用 `TO_AGENT`
6. **复用点**：需要定点重跑时，明确哪些上游 artifact 应该被 `--from` / `--resume` 复用
7. **兜底链**：多个候选方案用同层 `serial`，不要在一个 Node 里堆 if

动手前先给出：`输入 -> DAG -> 产物`。这个设计不清楚时，先问用户，不要猜。

## 核心心智模型

1. **DAG 拓扑执行**：节点 `run(ctx)` 返回 artifact，下游用 `ctx.get("upstream_id")` 读取；同轮就绪节点并行
2. **暂停 / 续跑**：`checkpoint=TO_HUMAN` 等人确认，`TO_AGENT` 等外部 agent 写产物；`--out` + `--from` / `--resume` 复用上游
3. **扇出 / 兜底**：`replicas` 静态副本，`FanOut` 动态扇出，`serial` 控制同层 fallback 顺序

## 开始使用

```bash
pip install esflow
esflow new my_skill
python my_skill/scripts/run.py --out ./runs/a
```

最小验收：`runs/a/<node>/` 有业务产物，`runs/a/.esflow/<node>/artifact.json` 有结构化 artifact。

标准结构：

```text
my_skill/
  SKILL.md
  scripts/
    flow.py      # 声明 nodes / edges / replicas / dynamic / serial
    run.py       # 入口，集成 pass_check 和 esflow_event
    nodes/       # 一个文件一个 Node，id 非空唯一
```

常规开发只改三处：`flow.py` 声明 DAG，`nodes/` 增加 Node，`run.py` 增加业务预检。

## 入口建议

新 skill 默认用 `run_flow_script(...)` 写入口，自动获得 `--out` / `--resume` 行为。需要自定义 stdout envelope、复杂清理、二次 TO_AGENT 编排时，才保留手写 `Runner.load(...)` 入口。

```python
from pathlib import Path
import argparse
import asyncio

from esflow import run_flow_script


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--format", default="md")
    return parser


def build_node_args(args):
    if not args.resume and not args.input:
        raise SystemExit("--input required on first run")
    return {
        "parse": {"input": args.input},
        "export": {"format": args.format},
    }


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_flow_script(
        Path(__file__).parent,
        parser=build_parser(),
        node_args_builder=build_node_args,
    )))
```

`Runner.load(node_args=...)` 首跑会写入 `.esflow/node_args.json`。`--resume` 默认继承首跑入参；本次传入同名字段才覆盖。不要在 resume 分支传 parser 默认值构造出的完整 `node_args`。需要 resume 的业务参数不要写成必填位置参数，改用可选参数并只在首跑校验。

## TO_AGENT 最小模式

```python
from esflow import Node, Checkpoint


class AgentWrite(Node):
    id = "agent_write"
    checkpoint = Checkpoint.TO_AGENT

    def deliver(self, artifact) -> bool:
        return "summary.txt" in artifact.get("files", [])
```

```bash
python3 scripts/run.py --out ./runs/a   # 退出码 2,stderr 提示 node_dir
echo "done" > ./runs/a/agent_write/summary.txt
python3 scripts/run.py --resume ./runs/a
```

## 关键规则

- `run(ctx)` 必须返回 artifact，通常是 `dict`
- 大文件写 `self.output_dir`，artifact 只保存路径和元数据
- `accept=False` 是合法 skip，下游继续；`deliver=False` 是产物错误，流程失败
- `ctx.get("id")` 取单个上游；`ctx.gather("base")` 只收同 base 副本
- `self.depth` 是拓扑深度，入口节点为 0；同层节点 depth 相同，静态/动态副本继承 base depth
- 跨 base 兜底链用 `ctx.upstream_ids()` 或 `ctx.layer(self.depth)`，别用 `gather`
- `replicas` 用于加载期已知副本数；`FanOut` 用于运行时动态副本数
- `serial` 是同层调度顺序，不是副本数
- `--from` / `--from-depth` 必须搭配 `--out`；`--resume` 只用于 TO_AGENT 产物写完后续跑，并自动继承首跑 `node_args`
- 首跑传了 `--out ./runs/a` 或业务参数后，`--resume ./runs/a` 不需要重复传；只有明确覆盖时才传同名 `node_args`
- `nodes/*.py` 顶层可以 import `esflow` 和标准库；第三方库、外部 SDK、业务重依赖放进 `run` 或预检函数，否则预检无从触发
- `esflow view` 和 `esflow debug` 都是交互式 web 服务，不是文本拓扑输出；无 GUI 或远程 SSH 没有端口转发时不适合依赖它们

## 常用命令

```bash
esflow view ./my_skill/scripts
esflow run ./my_skill/scripts --out ./runs/a
esflow run ./my_skill/scripts --out ./runs/a --from translate
esflow run ./my_skill/scripts --out ./runs/a --from-depth 2
esflow run --resume ./runs/a
esflow debug ./my_skill/scripts
esflow debug ./my_skill/scripts --node worker#2
esflow debug ./my_skill/scripts --clear
```

需要具体代码写法、TO_HUMAN / TO_AGENT、静态并行、动态扇出、兜底链、预检、模板一致性和调试限制时，阅读 `[reference.md](reference.md)`。