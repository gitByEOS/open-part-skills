# esflow 使用参考

这份文档讲清楚如何用 esflow 写一个可运行、可暂停、可续跑的 Python DAG workflow。它不依赖外部示例；按顺序读完即可开始写。

## 1. 最小开发路径

先生成标准结构：

```bash
pip install esflow
esflow new my_skill
python my_skill/scripts/run.py
```

目录职责固定：

```text
my_skill/
  SKILL.md
  scripts/
    flow.py      # 声明 DAG 拓扑
    run.py       # 运行入口，做预检和事件渲染
    nodes/       # 一个文件一个 Node 子类
```

日常开发只改三类文件：

1. 在 `flow.py` 声明节点顺序、边、并行、动态扇出、同层串行策略
2. 在 `nodes/` 写节点，每个节点实现 `run(ctx)` 并返回 artifact
3. 在 `run.py` 增加启动前检查，例如服务健康检查、依赖检查、输入文件检查

生产推荐的 `run.py` 风格：`pass_check(...)` 放在 `try/except FlowCheckError` 内，失败时打印错误并返回退出码 1。检查函数推荐返回 `CheckResult | None`，需要快速写法时也可返回 `str | None`，但同一项目内不要混用两种风格。`esflow new` 生成的 demo 是最小可跑版本（裸 `pass_check` + `str | None`），生产场景按本节示例升级。

## 2. 声明一个 flow

`@flow` 把普通类转成 DAG 定义。`nodes` 写 base id，`edges` 写数据依赖。

```python
from esflow import flow, edge

@flow(id="article_flow", title="文章处理")
class ArticleFlow:
    nodes = ["fetch", "parse", "review", "export"]
    edges = [
        edge("fetch", "parse"),
        edge("parse", "review"),
        edge("review", "export"),
    ]
```

常用类属性：

- `nodes`: 节点 base id 列表，必须能在 `nodes/` 找到同 id 的 `Node`
- `edges`: 有向边列表，表达上游到下游的依赖
- `replicas`: 静态副本数，例如 `{"worker": 5}`
- `dynamic`: 动态扇出 base 集合，例如 `{"worker"}`
- `serial`: 同层串行 base 集合，用来写兜底链

加载时会校验：

- `flow.py` 有且仅有一个 `@flow`
- `nodes/*.py` 每个文件有且仅有一个 `Node` 子类
- `Node.id` 非空且唯一
- `flow.nodes`、`replicas`、`dynamic`、`serial` 都能找到对应 Node
- `replicas` 与 `dynamic` 不能声明同一个 base
- 静态展开后的 DAG 不能有环

## 3. 写一个 Node

Node 是最小执行单元。`run(ctx)` 必须实现，返回 artifact，通常是 `dict`。

```python
from esflow import Node

class Fetch(Node):
    id = "fetch"
    title = "抓取文章"

    def run(self, ctx) -> dict:
        return {"url": "https://example.com/a", "html": "<html>...</html>"}
```

下游用 `ctx.get("upstream_id")` 读取上游 artifact：

```python
from esflow import Node

class Parse(Node):
    id = "parse"

    def run(self, ctx) -> dict:
        fetch = ctx.get("fetch")
        return {"text": fetch["html"].replace("<html>", "").replace("</html>", "")}
```

大文件不要直接塞进 artifact。写到 `self.output_dir`，artifact 只保存路径和元数据：

```python
from esflow import Node

class Export(Node):
    id = "export"

    def run(self, ctx) -> dict:
        text = ctx.get("parse")["text"]
        path = self.output_dir / "result.txt"
        path.write_text(text + "\n", encoding="utf-8")
        return {"out_path": str(path), "chars": len(text)}
```

### 产物目录约定

`self.output_dir` 由 Runner 注入，默认路径：

```text
<job_dir>/<rid>/
```

`job_dir` 的默认值由运行模式决定：

- **库式 / `esflow run`（无 `--out`）**：`/tmp/esflow/outputs/<flow_id>/<job_id>/`（系统自动清理，不长期保留）
- **`esflow run --out <dir>`**：`<dir>/`（用户指定，长期保留，用于续跑）
- **`esflow debug`**：`/tmp/esflow/debug/<flow_id>/`（固定路径，累积复用上游产物）

`<job_id>` 是时间戳 + 4 位短 hash（如 `20260708-205516-0v5s`），每次 `esflow run`（无 `--out`）生成新的；指定 `--out` 时 `job_dir` 就是 `--out` 目录本身，没有 `<job_id>` 层级。

所以一次普通跑的完整产物路径长这样：

```text
/tmp/esflow/outputs/weather_flow/20260708-205516-0v5s/
├── .esflow/                    # 框架元数据（v0.1.3 隔离）
│   ├── parse_args/artifact.json
│   ├── geocode/artifact.json
│   └── ...每个节点一个
├── parse_args/                 # 业务产物（节点自己写的文件）
├── geocode/
└── export/weather_report.md
```

跑完不知道去哪找文件时，看事件流里 `final` event 的 artifact（含 `out_path`），或直接进 `job_dir/<rid>/` 翻。自定义 `output_dir`（在 `accept` 里设 `self.output_dir = Path("...")`）可指向业务目录，框架尊重节点自定义，常用于 TO_AGENT 节点让 agent 写到固定业务路径。

## 4. accept 和 deliver

`accept(ctx)` 在 `run` 前执行，用来判断节点是否应该运行。

```python
def accept(self, ctx) -> bool:
    return bool(ctx.get("fetch")["html"])
```

`accept=False` 是合法 skip：节点 artifact 为 `None`，下游继续推进。

`deliver(artifact)` 在 `run` 后执行，用来校验产物。

```python
def deliver(self, artifact) -> bool:
    return artifact["chars"] > 0
```

`deliver=False` 是错误：流程进入 error。

判断规则：

- 前置条件不满足，但流程可以继续：用 `accept=False`
- 产物不合格，不能继续：用 `deliver=False`
- 程序异常、外部调用失败：抛异常，让流程失败

## 5. ctx 取数规则

`ctx` 是节点读取上游产物的唯一入口。

- `ctx.get("fetch")`: 取单个上游 artifact；上游 skip 时返回 `None`
- `ctx.gather("worker")`: 收集同 base 的所有副本 artifact，按 index 排序
- `ctx.upstream_ids()`: 获取所有已完成上游 id，适合跨 base 兜底链
- `ctx.layer(self.depth)`: 获取同层前序结果，适合判断 fallback 是否接手

`self.depth` 由 Runner 初始化时按 DAG 拓扑写入：入口节点 depth 为 0；依赖入口的下一层为 1；同一轮可就绪的节点通常处在同一 depth。静态副本 `worker#0..N` 和动态 `FanOut` 副本继承 base 节点 depth，所以同层兜底链可以用 `ctx.layer(self.depth)` 看前序节点或副本是否已经产出。

普通链路用 `ctx.get`：

```python
parse = ctx.get("parse")
```

多上游扇入（DAG 最常见模式）直接分别 `ctx.get` 各取各的：

```python
class Aggregate(Node):
    id = "aggregate"

    def run(self, ctx) -> dict:
        current = ctx.get("fetch_current")
        forecast = ctx.get("fetch_forecast")
        return {"current": current, "forecast": forecast}
```

扇入副本用 `ctx.gather`：

```python
results = ctx.gather("worker")
```

跨 base 兜底链用 `ctx.upstream_ids()` 或 `ctx.layer(...)`，不要用 `gather`。

## 6. 运行入口 run.py

`run.py` 的职责是先做预检，再加载 flow，再消费事件流。

```python
import asyncio
import sys
from pathlib import Path

from esflow import Runner, esflow_event
from esflow.check import CheckResult, FlowCheckError, pass_check


def check_input_dir() -> CheckResult | None:
    input_dir = Path("input")
    if input_dir.exists():
        return None
    return CheckResult(reason="缺少 input 目录", fix="mkdir input")


async def main() -> int:
    try:
        pass_check(check_input_dir)
    except FlowCheckError as exc:
        print(exc, file=sys.stderr)
        return 1

    runner = Runner.load(str(Path(__file__).parent))
    async for event in runner.run():
        esflow_event(event)
    return 0 if runner.state.status != "error" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

`from esflow import Node`、`Checkpoint`、`FanOut` 这类框架 import 必须放在 `nodes/*.py` 顶层，标准库 import 也可以放顶层。第三方库、外部 SDK、业务重依赖放进 `run` 方法或检查函数里，否则 loader 还没跑预检就会 `ImportError`。

### 高层 API：run_to_break + to_envelope

上面是手写 `async for event in runner.run()` + 自己判断 event 类型的写法。若 skill 入口只关心"跑到断点停下 → 拿退出码和 envelope"，用高层 API 一行消掉胶水：

```python
import asyncio
import json
import sys
from pathlib import Path

from esflow import Runner, esflow_event
from esflow.check import CheckResult, FlowCheckError, pass_check


def check_input_dir() -> CheckResult | None:
    if Path("input").exists():
        return None
    return CheckResult(reason="缺少 input 目录", fix="mkdir input")


async def main() -> int:
    try:
        pass_check(check_input_dir)
    except FlowCheckError as exc:
        print(exc, file=sys.stderr)
        return 1

    runner = Runner.load(str(Path(__file__).parent))
    events, kind, break_event = await runner.run_to_break()
    for ev in events:
        esflow_event(ev)

    exit_code, envelope = Runner.to_envelope(kind, break_event)
    print(json.dumps(envelope, ensure_ascii=False), file=sys.stderr)
    if kind == "error" and break_event is not None:
        raise break_event.as_exception()
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

`BreakKind` 三种：

- `end`: job 正常结束，break_event 是 end event（或 None）
- `to_agent`: TO_AGENT checkpoint，break_event 含 `resume_hint`
- `error`: 节点抛异常，`break_event.as_exception()` 还原成原异常类型

`to_envelope` 映射：

- `end` → `(0, {"status": "end"})`
- `to_agent` → `(2, {"status": "to_agent", "node_id":..., "resume_hint":...})`
- `error` → `(1, {"status": "error", "message":..., "exc_type":..., "exc_attrs":...})`

`JobEvent.as_exception()` 还原异常：同进程优先返回原 `exc` 引用（类型/属性/身份全保留）；跨进程（只有 `exc_type` + `exc_attrs`，无 `exc`）按全名 import 类，`__new__` 绕过 `__init__` 实例化并回填 `__dict__`；import 失败降级 `RuntimeError`。

TO_HUMAN checkpoint 不算断点（等 stdin 控制信号），view/debug 流式场景仍需直接 `async for event in runner.run()`。

### 节点入参注入

节点常需要从 CLI / 配置读参数（模型名、并发数、输入路径）。别把这些塞进 flow 声明，用 `Runner.load(flow_dir, node_args={...})` 注入，节点从 `self.kwargs` 读：

```python
class Translate(Node):
    id = "translate"

    def run(self, ctx) -> dict:
        model = self.kwargs.get("model", "gpt-4o-mini")
        text = ctx.get("parse")["text"]
        return {"translated": translate(text, model=model)}
```

```python
runner = Runner.load(
    str(Path(__file__).parent),
    node_args={"translate": {"model": "claude-3-5-sonnet"}},
)
```

`node_args` 的 key 是 base id，匹配 base 与所有副本（`base#i`）。动态扇出副本在 `_expand_fanout` 创建时继承 base 的入参。

`kwargs` 是输入不是产物，**不进 `artifact.json`**，`--resume` 续跑时框架不持久化它——由 skill 在 `Runner.load` 时显式重传。

## 7. 静态并行 replicas

esflow 的并行是 DAG 拓扑级行为：同一轮就绪的节点（同 depth、上游都已 done/skipped）自动 `asyncio.gather` 并行跑，不需要声明。`replicas` 和 `FanOut` 只是制造多个同层副本，并行调度本身是框架免费给的。

并行在事件流里的表现：同层节点的 `queued` / `running` 事件交错出现，`final` artifact 顺序不保证（谁先完成谁先 emit）。stdout 是线性打印，看到交错事件就说明在并行，不要用"artifact 严格按声明顺序"判断是否并行。

副本数在加载时已知时，用 `replicas`。

```python
@flow(id="batch_flow")
class BatchFlow:
    nodes = ["fetch", "worker", "merge"]
    edges = [edge("fetch", "worker"), edge("worker", "merge")]
    replicas = {"worker": 5}
```

loader 会把 `worker` 展开成 `worker#0` 到 `worker#4`，并自动改写扇出和扇入边。

worker 用 `self.index` 取自己的分片：

```python
class Worker(Node):
    id = "worker"

    def run(self, ctx) -> dict:
        chunks = ctx.get("fetch")["chunks"]
        chunk = chunks[self.index]
        return {"items": [x * 2 for x in chunk]}
```

merge 用 `ctx.gather("worker")` 收集所有副本：

```python
class Merge(Node):
    id = "merge"

    def run(self, ctx) -> dict:
        results = ctx.gather("worker")
        return {"count": sum(len(r["items"]) for r in results)}
```

## 8. 动态扇出 FanOut

副本数依赖运行时产物时，用 `dynamic` + `FanOut`。

```python
@flow(id="dynamic_flow")
class DynamicFlow:
    nodes = ["ingest", "split", "worker", "merge"]
    edges = [
        edge("ingest", "split"),
        edge("split", "worker"),
        edge("worker", "merge"),
    ]
    dynamic = {"worker"}
```

split 节点返回 `FanOut`，不产普通 artifact：

```python
from esflow import FanOut, Node

class Split(Node):
    id = "split"

    def run(self, ctx) -> FanOut:
        chapters = ctx.get("ingest")["chapters"]
        return FanOut(base="worker", payload=chapters)
```

动态 worker 用 `self.fanout_payload` 取载荷：

```python
class Worker(Node):
    id = "worker"

    def run(self, ctx) -> dict:
        chapter = self.fanout_payload
        return {"translated": translate(chapter)}
```

限制：

- 同一个 base 不能同时放进 `replicas` 和 `dynamic`
- 动态副本节点不挂 checkpoint
- 动态副本展开前不存在，单点调试通常停在 split 或 merge

## 9. 暂停给人 TO_HUMAN

节点跑完后需要人工确认，就加 `checkpoint = Checkpoint.TO_HUMAN`。

```python
from esflow import Checkpoint, Node

class Review(Node):
    id = "review"
    checkpoint = Checkpoint.TO_HUMAN

    def run(self, ctx) -> dict:
        return {"reviewed": ctx.get("parse"), "ok": True}
```

CLI 暂停后输入：

- `c`: continue，继续下游
- `r`: retry，从当前节点重跑
- `a`: abort，中止流程

库式调用：

```python
runner.resume()
runner.retry(from_node="review")
runner.abort()
```

## 10. 暂停给 Agent TO_AGENT

需要外部 agent 写产物时，用 `Checkpoint.TO_AGENT`。这种节点不实现 `run`，只用 `deliver` 校验 agent 写入的文件。

```python
from esflow import Checkpoint, Node

class AgentSummary(Node):
    id = "agent_summary"
    checkpoint = Checkpoint.TO_AGENT

    def deliver(self, artifact) -> bool:
        return "summary.txt" in artifact.get("files", [])
```

默认产物目录是 `<job_dir>/<rid>/`。若想把 agent 产物写到业务目录，在 `accept` 里设 `self.output_dir`，框架尊重节点自定义：

```python
class AgentSummary(Node):
    id = "agent_summary"
    checkpoint = Checkpoint.TO_AGENT

    def accept(self, ctx) -> bool:
        self.output_dir = Path("workspace/summary")
        return True

    def deliver(self, artifact) -> bool:
        return "summary.txt" in artifact.get("files", [])
```

完整链路：

```bash
esflow run ./my_skill/scripts --out ./runs/a
# 流程跑到 agent_summary 后退出，返回码为 2
# 外部 agent 写文件到 ./runs/a/agent_summary/summary.txt
esflow run --resume ./runs/a
```

`--resume` 会扫描 TO_AGENT 节点目录（过滤点开头文件），构造 artifact：

```python
{"output_dir": ".../agent_summary", "files": ["summary.txt"]}
```

agent 不需要手写 `artifact.json`。框架元数据（`artifact.json` / `break_to_agent.json` / `flow_dir.txt`）隔离在 `<job_dir>/.esflow/` 下，业务产物目录只装 agent 写的文件，agent 不要往 `.esflow/` 里写。

库式调用拿到 checkpoint event 时，用 `Runner.to_agent_hint(event, resume_cmd)` 直接打印介入指引，无需手拼字符串：

```python
resume_cmd = "esflow run ./my_skill/scripts --resume {job_dir}"
print(Runner.to_agent_hint(event, resume_cmd=resume_cmd), file=sys.stderr)
# 输出：
# [to_agent] 写产物到:./runs/a/agent_summary
# [to_agent] 上游产物:{...}
# [to_agent] 完成后续跑:esflow run ./my_skill/scripts --resume ./runs/a
```

`resume_cmd` 必须含 `{job_dir}` 占位符，框架填好。`event.resume_hint` 由框架在 checkpoint 时填好（`node_dir` / `upstream_artifact` / `job_dir` / `node_id`）。

## 11. 兜底链 serial

同层多个节点只能按顺序尝试时，用 `serial`。它是调度策略，不是副本数。

```python
@flow(id="fallback_flow")
class FallbackFlow:
    nodes = ["decide", "fetch_a", "fetch_b", "merge"]
    edges = [
        edge("decide", "fetch_a"),
        edge("decide", "fetch_b"),
        edge("fetch_a", "merge"),
        edge("fetch_b", "merge"),
    ]
    serial = {"fetch_a", "fetch_b"}
```

第一个源能处理就跑，不能处理就 skip：

```python
class FetchA(Node):
    id = "fetch_a"

    def accept(self, ctx) -> bool:
        target = ctx.get("decide")["target"]
        return target.startswith("https://a.example")
```

第二个源检查同层前序是否已有成功产物，有就 skip，没有就接手：

```python
class FetchB(Node):
    id = "fetch_b"

    def accept(self, ctx) -> bool:
        for artifact in ctx.layer(self.depth):
            if artifact:
                return False
        return True
```

merge 从真实成功的上游取产物：

```python
class Merge(Node):
    id = "merge"

    def run(self, ctx) -> dict:
        for upstream_id in ctx.upstream_ids():
            artifact = ctx.get(upstream_id)
            if artifact:
                return {"source": upstream_id, "data": artifact["data"]}
        return {"source": None, "data": None}
```

## 12. 续跑和定点重跑

默认运行只在内存保留 artifact。要续跑，必须先用 `--out` 落盘。

```bash
esflow run ./my_skill/scripts --out ./runs/a
```

从某个节点重跑到末端：

```bash
esflow run ./my_skill/scripts --out ./runs/a --from translate
```

从某个拓扑深度重跑：

```bash
esflow run ./my_skill/scripts --out ./runs/a --from-depth 2
```

TO_AGENT 写完产物后续跑：

```bash
esflow run --resume ./runs/a
```

规则：

- `--from` / `--from-depth` 必须搭配 `--out`
- `--resume` 独占，不和 flow dir、`--from`、`--node` 混用
- `--from` 需要目标节点上游已经有落盘 artifact
- 改了某节点代码，通常从该节点开始 `--from`
- 只人工改了某节点输出文件，通常从它的下游开始 `--from`
- `artifact.json` 落在 `<job_dir>/.esflow/<rid>/`，业务产物目录 `<job_dir>/<rid>/` 只装节点写的文件；删 job_dir 时整目录一起清，不要单独删 `.esflow/`

## 13. 单点调试

`esflow view` 和 `esflow debug` 都会启动同一个交互式 web 服务。它们不是文本模式命令，不会在 stdout 打印拓扑；无 GUI、远程 SSH 没有端口转发时不可用。

v0.1.3 起 `view` / `debug` 端口默认 `0`，由 OS 分配可用端口，多实例并行不冲突，固定端口 8765 被占用导致 OSError 的问题已消除。启动后实际 URL 会打印到 stdout（形如 `esflow view (debug) → http://127.0.0.1:<port>`）。

打开 web 视图看 DAG 和事件流：

```bash
esflow view ./my_skill/scripts
```

打开 web debug 模式：

```bash
esflow debug ./my_skill/scripts
```

只调某个节点：

```bash
esflow debug ./my_skill/scripts --node worker#2
```

清空 debug 产物：

```bash
esflow debug ./my_skill/scripts --clear
```

`run --node X` 与 `debug --node X` 不一样：

- `run --node X`: 跑 X 及必需上游
- `debug --node X`: 只跑 X，上游必须已经在 debug 目录有产物
- `view` / `debug`: 都依赖 web 服务；当前没有 fallback 文本模式

## 14. CLI 速查

```bash
esflow new NAME
esflow view FLOW_DIR
esflow run FLOW_DIR
esflow run FLOW_DIR --node X
esflow run FLOW_DIR --out DIR
esflow run FLOW_DIR --out DIR --from X
esflow run FLOW_DIR --out DIR --from-depth N
esflow run --resume DIR
esflow debug FLOW_DIR
esflow debug FLOW_DIR --node X
esflow debug FLOW_DIR --clear
```

返回码：

- `0`: job 跑到 end
- `1`: error、预检失败、参数错误
- `2`: 跑到 TO_AGENT checkpoint，等待外部产物
- `130`: Ctrl+C 中断

## 15. 常见错误

- 把第三方库、外部 SDK、业务重依赖 import 放在 `nodes/*.py` 顶层，导致预检无法触发
- 把 `from esflow import Node` 也塞进 `run` 方法，导致 Node 类无法被 loader 发现
- 把大文件直接放进 artifact，导致 JSON 产物膨胀
- 用 `deliver=False` 表达“这个节点不用跑”，应该用 `accept=False`
- 兜底链跨 base 用 `ctx.gather`，应该用 `ctx.upstream_ids()` 或 `ctx.layer`
- 忘记 `--out` 就想 `--from` 续跑
- 在无 GUI 或远程 SSH 没有端口转发的环境里依赖 `view` / `debug`
- 动态副本上挂 checkpoint
- 同一个 base 同时声明 `replicas` 和 `dynamic`
- 以为 `serial` 是副本数；它只是同层启动顺序
