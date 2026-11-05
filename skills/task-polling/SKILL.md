---
name: task-polling
description: 以 docs/task.md 为唯一事实源，使用 /loop 自动领取、执行和完成单个本地任务
version: 1.1.0
dependencies:
  - "python3"
---

# Task Polling

## 用途

用户只维护项目根目录的 `docs/task.md`，不需要额外任务 JSON。文档固定包含五个区段：

```text
# 任务计划
## 未领取
## 进行中
## 已完成
## 远期规划
## 确认不做
```

用户把可执行任务放入 `未领取`，任务必须使用唯一 ID；标题支持半角或全角冒号。用户只写目标。领取后，任务行写下初始环境的短 commit，之后不再改：

```markdown
- [ ] TASK-001: 分析这个仓库，都有哪些核心模块
- [ ] TASK-002：修复按钮纵向不居中问题
```

轮次只记录 agent 当时的理解，以及本轮改过的开发文档和源码目录。未通过原因写在上一轮。下一轮对照任务行上的目标和未通原因继续进行：

```markdown
- [ ] TASK-001 [a1b2c3d]: 分析这个仓库，都有哪些核心模块
  - 轮次1：agent对任务的理解；<dirs:docs;src;>；未通过原因
  - 轮次2：agent对任务的理解；<dirs:docs;>
```

区段中的 `- [ ]` 空占位行会被忽略，不会成为任务

`远期规划` 和 `确认不做` 由用户维护，Agent 不会自动领取其中内容。

## 调度规则

当用户要求开始、继续或轮询任务时，按以下协议工作：

- **准备**：先执行 `status`，读取当前任务状态

  ```bash
  python3 <skill>/scripts/task_polling.py --json status
  ```

- **轮询**：使用 `/loop` 每 2 分钟检查一次，每轮执行 `claim`

  ```bash
  python3 <skill>/scripts/task_polling.py --json claim
  ```

- **领取**：返回 `claimed` 时，任务行已带初始环境的短 commit。通读 `task.description`，先形成自己的任务理解，再执行
- **续办**：返回 `error` 时，依据 `task.description` 继续当前任务，不得重复领取
- **空闲**：返回 `idle` 时，等待下一轮 `/loop`
- **打断**：收到新用户消息时，停止轮询并优先响应

`task` 字段为 `id`、`title`、`description`、`checked`。
完成或返工分别使用 `complete`、`reopen`，仅限当前会话，不创建 Cron。
理解写入对应轮次，写 agent 怎么看这个任务。本轮改动写成 `<dirs:目录;目录;>`。

不要在任务执行期间重复领取任务。

## 完成规则

只有任务已经做完才允许完成。完成前只需把本轮改过的开发文档和源码目录 add，其他文件可以继续留着。开发文档和源码指 `docs`、`src`、`scripts`，以及仓库根目录上的文档和源码文件。`--understanding` 写本轮 agent 理解：

```bash
python3 <skill>/scripts/task_polling.py --json complete --id TASK-001 --understanding "agent对任务的理解"
```

没有轮次时写入 `轮次1`。已有本轮时更新这轮理解和改动目录，不在本轮写未通过原因。任务行上的初始 commit 保持不变。任务移入 `已完成` 并标记为 `[x]`：

```markdown
- [x] TASK-001 [a1b2c3d]: 分析这个仓库，都有哪些核心模块
  - 轮次1：agent对任务的理解；<dirs:docs;src;>
```

需要返工时，从 `已完成` 拿回 `进行中`。未通过原因追加到上一轮改动目录之后，再写下本轮理解：

```bash
python3 <skill>/scripts/task_polling.py --json reopen --id TASK-001 --understanding "agent对任务的理解" --reason "未通过原因"
```

```markdown
- [ ] TASK-001 [a1b2c3d]: 分析这个仓库，都有哪些核心模块
  - 轮次1：agent对任务的理解；<dirs:docs;src;>；未通过原因
  - 轮次2：agent对任务的理解
```

返工对照任务行上的目标和未通原因继续进行，过程中的提交不需要记。

该命令仅处理 `已完成` 任务。执行中尚未完成时留在 `进行中` 继续做，不要先完成再返工。

## 边界

- `docs/task.md` 是唯一任务状态源，不读取或写入外部 JSON
- 一次最多一个 `进行中` 任务
- 不把远期规划任务提前执行
- 不擅自清理 `已完成` 任务，用作发版前 `CHANGELOG` 回顾
- 轮次由 `complete`、`reopen` 写入，旧轮次保留
- 完成时只添加本轮的开发文档和源码目录，不要求整个工作区干净
- 初始环境的短 commit 只写在任务行，领取后不再改，用于复现工作环境迭代 `Rules`
- 不擅自发布、推送、删除数据或调用外部服务
