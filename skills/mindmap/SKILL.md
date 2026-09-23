---
name: mindmap
description: 把「标题 + 缩进列表」结构的 Markdown 文档转成单文件可视化大纲树，支持搜索高亮、层级展开、板块导航、明暗切换。用户提到「思维导图」「大纲可视化」时使用。
version: 1.0.0
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# mindmap

把缩进列表结构的 Markdown 转成漂亮的单文件 HTML 可视化网页

## 用法

```bash
python3 <skill>/scripts/md2mindmap.py <输入.md> [-o 输出.html] [--theme dark|light]
```

- 默认输出到源文件同目录，命名 `<原名>.mindmap.html`
- 默认全部展开，页面内可用 L1/L2/L3 按钮收起
- 输出为单文件 HTML，仅依赖 Python 标准库，直接双击打开
- 只读取指定的本地 Markdown 与 Skill 自带模板，写入指定输出路径；默认写到源文件同目录，如文件已存在会覆盖，请先确认路径
- 不访问网络；生成内容按纯文本处理标题、引言和节点，不执行输入 Markdown 中的 HTML 或脚本
- 不支持图片、表格、代码块与标准 Markdown 富文本，列表外的文字只在首个节点之前作为引言显示

## 支持的输入结构

- `# 标题` → 页面标题
- `> 引言`（列表前的引用行）→ 头部引言
- `-`  或 `*`  缩进列表（2 空格一级）→ 树节点
- 其余行忽略；多个一级列表自动包一层虚拟根

需要先写 md 再可视化时，必须先读写作模板 [assets/doc-template.md](assets/doc-template.md)，严格按模板结构产出

## 输入示例

```markdown
# 项目路线图

> 本周进度

- 研发
  - 接口
  - 测试
    - 自动化
- 发布
  - 发布检查
```

运行 `python3 <skill>/scripts/md2mindmap.py 路线图.md`，生成同目录的 `路线图.mindmap.html`。
打开网页后可搜索节点、按层级折叠，或切换明暗主题。
注：统计中的节点数包含多个一级板块自动生成的虚拟根。
此 Skill 随附页面模板、样式与交互脚本，生成时会内联到输出 HTML。
