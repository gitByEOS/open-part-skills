---
name: switch-chat
version: 1.0.0
description: 当用户需要切换会话并交接任务时使用，生成可视化交接文档，确保新会话能无缝继承工作目标
license: MIT
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# Switch Chat

任务交接 Skill，直接传文本生成可编辑的可视化 HTML。

## 生成交接文档

### Agent 用法（heredoc 直接传文本）

```bash
python3 {skill}/scripts/gen.py --open << 'EOF'
# 任务交接：用户中心重构

## 工作目标
用户中心模块正在从 REST API 迁移到 GraphQL。

## 当前进度
- [x] 完成 Schema 设计
- [ ] 实现 resolver

## 注意事项
测试库用 .env.test。
EOF
```

### 从已有文件填充

```bash
python3 {skill}/scripts/gen.py --from handoff.md --open
```

## 页面操作

打开后直接在浏览器中编辑：点击任意文本输入、添加/删除行、切换完成状态。

- 点击「回写」：把当前页面内容写回 `{skill}/assets/continue.html`，并复制 `/switch-chat 继续` 到剪贴板
- 点击「复制」：复制当前交接 Markdown 到剪贴板
- 点击「导出文件」：下载 `switch-chat.md`

`--open` 会启动本地回写服务，5 分钟无回写会自动退出。

## 新会话读取

当用户输入 `/switch-chat 继续` 时，必须执行：

```bash
python3 {skill}/scripts/read.py
```

执行后按输出的结构化交接文本继续工作：

1. 先确认是否包含「工作目标」「当前进度」「注意事项」
2. 如果读取失败，明确提示 `{skill}/assets/continue.html` 不存在或未回写

