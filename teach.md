

# 📚 技能分发教程（基于 `skills` CLI）

## 1. 设计技能目录结构

`skills` CLI 会递归查找所有直接包含 `SKILL.md` 的文件夹（最多深度 2 级）。推荐以下两种结构：

### 1.1 单技能（简单）

```
仓库根目录/
└── SKILL.md
```

此时技能名就是 `SKILL.md` 所在的文件夹名，如果位于根目录，技能名等价于 `仓库名`（但一般不推荐，因为不够直观）。更推荐用文件夹包裹：

```
仓库根目录/
└── my-first-skill/
    └── SKILL.md
```

这样技能名就是 `my-first-skill`，用户可通过 `--skill my-first-skill` 安装。

### 1.2 多技能（推荐）

```
仓库根目录/
├── skill-a/
│   └── SKILL.md
├── skill-b/
│   ├── SKILL.md
│   └── helper.py         (附属文件)
└── skill-c/
    └── SKILL.md
```

## 2. 本地测试（非常重要）

在推送到 GitHub 之前，先用本地路径测试能否被 `skills` CLI 识别。

```bash
# 回到仓库的上一级目录
cd ..

# 列出本地仓库中的所有技能
npx skills add ./仓库名 --list
```

如果一切正常，你会看到类似输出：

```
Skills found in ./my-repo:
  - skill-a
  - skill-b
  - skill-c
```

如果某个技能没有被列出，检查：
- 目录深度是否超过 2 层（例如 `skill-a/nested/SKILL.md` 不被识别）
- `SKILL.md` 文件名大小写是否正确（必须是全大写 `SKILL.md`）
- YAML frontmatter 格式是否正确（`---` 必须单独一行，前后不能有空格）

## 3. 他人如何使用

你的仓库公开后，任何人都可以通过以下方式安装技能：

### 3.1 列出仓库中所有可用技能

```bash
npx skills add https://github.com/你的用户名/仓库名 --list
```

### 3.2 安装单个技能

```bash
npx skills add https://github.com/你的用户名/仓库名 --skill skill-a
```

### 3.3 同时安装多个技能

```bash
npx skills add https://github.com/你的用户名/仓库名 --skill skill-a --skill skill-b
```

### 3.4 安装到特定 AI 工具（跳过交互选择）

```bash
npx skills add https://github.com/你的用户名/仓库名 --skill skill-a --agent cursor
```

支持的 `--agent` 可选值通常有：`claude-code`、`cursor`、`windsurf`、`github-copilot` 等（取决于 `skills` CLI 版本）。

### 3.5 全局安装（所有项目可用）

```bash
npx skills add https://github.com/你的用户名/仓库名 --skill skill-a -g
```

## 4. 更新你的技能

当你修改了某个 `SKILL.md` 或添加了新技能后，用户需要重新运行安装命令。`skills` CLI 会覆盖旧版本（但会提示）。

建议在 README 中告知用户使用 `npx skills add ...` 重新安装即可更新。
