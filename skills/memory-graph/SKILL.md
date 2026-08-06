---
name: memory-graph
description: 使用全局 MemoryGraph 作为 Agent 外挂记忆图谱，使用 link 关联历史记忆；使用 patch 根据会话沉淀为记忆；用户主动写入记忆时使用 apply；需要查看或管理记忆时 look
version: 0.2.2
dependencies:
  - node
repository: https://github.com/gitByEOS/open-part-skills
---

# Memory Graph

## 前置条件

先确保 `memory-graph` 可执行：

- 已运行 `{Skill}/assets/install.sh`
- 执行 `memory-graph -v` 能输出版本号

## 动作

### link

根据用户要求查记忆图谱，并按历史记忆向用户描述你的理解，以及它会如何影响当前任务

```bash
memory-graph search "<关键词1[空格]关键词2 ...>" [--nodes 5]
```

### patch/apply

用户要求沉淀记忆时使用。
- patch时：先回顾会话历史，注意力放在**用户输入信息**
- apply时：先理解用户给出内容或用户的要求
- 然后执行以下步骤
1. 提炼可复用的结论、依据、规则、动作、经验或资产
2. 为方便用户编辑，先生成`/tmp/memory-apply.yaml`，为用户提供可点击的预览链接
3. 让用户查看编辑或给出优化方向
4. 收到确认写入指令后，再写入记忆图谱
5. 写入记忆图谱: `memory-graph apply /tmp/memory-apply.yaml`

示例：
```yaml
summary: 本轮会话摘要。
nodes:
  - id: note:worktree-reuse-node-modules
    type: Note
    title: worktree 复用 node_modules
    summary: >
      master 已有 node_modules 时，新 worktree 应软链复用，
      避免重复安装依赖。
    tags: [worktree, node_modules, symlink]
edges: []
```

### look

用户需要查看、清理或管理记忆时使用

```bash
memory-graph look
```
- 支持：总览、搜索、节点详情、更新/删除节点、删除关系

## 规则

- 存储固定使用全局 `~/.memory-graph`
- 节点只使用 `Concept`、`Note`、`Basis`、`Asset`、`Rule`、`Skill`、`Action`
- 节点可以写 `tags`，用于轻量索引和检索；tags 不建成节点
- 优先沉淀可复用结论，不写流水账，不把整段聊天原文写成节点
- patch 默认使用 YAML，字段保持 `summary / nodes / edges`，临时文件固定写入 `/tmp/memory-apply.yaml`
- 没有用户确认，不执行 `apply`

## 图模型

### 节点

| 类型 | 定义与用途 |
| --- | --- |
| `Concept` | 概念、模块、项目名、工具、命令、人物名... |
| `Basis` | 原始依据：用户指令、聊天记录、代码片段、报错、终端输出... |
| `Note` | 稳定结论、判断、经验，由 `Basis` 归纳而来 |
| `Asset` | 项目内部的文件、目录、命令、配置、接口、函数... |
| `Rule` | 规则、用户偏好、行为约束... |
| `Skill` | 工具调用经验、操作步骤、工作流... |
| `Action` | 具体到执行操作，但必须带动词和对象 |

### 边

| 边 | 含义 | 域（源） | 范围（目标） |
| --- | --- | --- | --- |
| `DESCRIBES` | 结论/规则描述对象特性 | Note, Rule | Concept, Asset |
| `BASED_ON` | 结论基于原始依据 | Note | Basis |
| `APPLIES_TO` | 规则/技能适用对象 | Rule, Skill | Concept, Asset |
| `REQUIRES` | 操作/技能依赖某条件或产物 | Action, Skill | Asset, Rule, Concept |
| `PRODUCED` | 操作产生产物或原始输出 | Action | Asset, Basis |
| `NEXT` | 流程中的下一步 | Skill, Action | Skill, Action |
| `USES` | 使用关系 | Action, Skill, Concept, Asset | Concept, Asset |
| `CONTAINS` | 层级包含 | Concept, Asset | Concept, Asset |
| `CAUSES` | 因果关系 | Action, Basis | Basis |
| `RELATES_TO` | 模糊关联，用于日记式管理 | 任意节点 | 任意节点 |
