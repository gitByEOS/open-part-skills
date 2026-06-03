---
name: skill-linker
description: 安装并使用 skill-link 命令，通过 fzf 搜索、多选并软链本地 skill/rule，用于多项目不同 skill 体系切换。用户提到 skill-link、链接 skill、安装本地 skills/rules 时使用
version: 1.0.0
dependencies:
  - fzf
repository: https://github.com/gitByEOS/open-part-skills
---

# Skill Linker

## 安装

运行安装脚本：

```bash
bash scripts/install.sh --root <path>
```

安装脚本会：

- 自动安装 `fzf`
- 写入 `SKILL_LINK_ROOT`
- 安装快捷命令 `skill-link`
- 写入当前 shell 的 rc 文件
- bash 下会检测 `.bashrc` 是否被登录配置加载；未加载时自动补 `source`

`SKILL_LINK_ROOT` 必须包含：

- `skills/`
- `rules/`

## 交互模式

```bash
skill-link
```

- 输入关键词搜索
- `Tab` 多选
- `←/→` 切换目标 Path
- `Enter` 链接或取消链接

## 非交互模式

```bash
skill-link --list --target cursor
skill-link --target cursor agents-chat-bridge chinese-language.mdc
```

### Agent 流程

1. Agent 先根据当前使用的编辑器判断目标 Path。
2. 判断规则：Cursor 使用 `cursor`，Claude Code 使用 `claude-code`，Codex 使用 `codex`。
3. 只有无法判断当前编辑器时，才使用 `AskQuestion` 让用户选择目标 Path。
4. 运行 `skill-link --list --target <path>` 获取候选项和状态。
5. 使用 `AskQuestion` 展示候选项，必须设置 `allow_multiple: true`。
6. 对用户选中的项目运行 `skill-link --target <path> <name...>`。

选中项执行切换行为：

- 当前已链接到同一来源：取消链接
- 当前未安装：创建软链
- 目标已存在且不是同一软链：报错并停止

## 环境变量

- `SKILL_LINK_ROOT`：本地 skill/rule 来源根目录

目标 Path 固定为：

- `~/.cursor`
- `~/.claude`
- `~/.codex`
