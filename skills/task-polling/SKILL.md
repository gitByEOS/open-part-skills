---
name: task-polling
description: 以 docs/task.md 为唯一事实源，使用 /loop 自动领取、执行和完成单个本地任务
version: 1.0.0
dependencies:
  - "python3"
repository: https://github.com/gitByEOS/open-part-skills
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

用户把可执行任务放入 `未领取`，任务必须使用唯一 ID；标题支持半角或全角冒号，正文可选：

```markdown
- [ ] TASK-001: 分析这个仓库，都有哪些核心模块
  - 验收&产物：生成一套wiki文档，每个模块一个md
  - 限制&约束：必须包含流程图和文件结构图

- [ ] TASK-002：修复按钮纵向不居中问题
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

- **领取**：返回 `claimed` 时，通读 `task.description` 后执行
- **续办**：返回 `error` 时，依据 `task.description` 继续当前任务，不得重复领取
- **空闲**：返回 `idle` 时，等待下一轮 `/loop`
- **打断**：收到新用户消息时，停止轮询并优先响应

`task` 字段为 `id`、`title`、`description`、`checked`。
完成或打回分别使用 `complete`、`reopen`，仅限当前会话，不创建 Cron。

不要在任务执行期间重复领取任务。

## 完成规则

只有代码、文档或脚本已经完成，并且任务正文中的验收已实际执行，才允许完成任务：

```bash
python3 <skill>/scripts/task_polling.py --json complete --id TASK-001 --summary "测试命令及结果"
```

完成命令会把任务完整移入 `已完成`，标记为 `[x]` 并追加完成结果。验收失败时，使用 `reopen` 打回 `进行中`，并保留完成记录：

```bash
python3 <skill>/scripts/task_polling.py --json reopen --id TASK-001 --reason "功能验收失败：具体问题"
```

该命令仅处理 `已完成` 任务。

## 边界

- `docs/task.md` 是唯一任务状态源，不读取或写入外部 JSON
- 一次最多一个 `进行中` 任务
- 不擅自发布、推送、删除数据或调用外部服务
- 不把远期规划任务提前执行
- 保留用户对 `docs/task.md` 拓展的编辑
- 不擅自清理 `已完成` 任务，用作发版前 `CHANGELOG` 回顾
