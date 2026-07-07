---
name: meet-record-html
description: 将面试/会谈问题 Markdown 生成为可现场填写纪要的单页 HTML（候选人徽章、问题标签、总结 textarea、临时追加问题、打印与导出 Markdown 按钮）。用户提到 meet-record-html、面试纪要、会谈纪要、面试问题转网页、面经 HTML 时使用。
version: 1.0.0
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# Meet Record to HTML

把面试/会谈问题 Markdown 导出为可现场填写总结、可临时追加问题的纪要 HTML

## 工作流

1. 按下方**输入格式**整理用户的文本或 Markdown
2. 执行生成脚本并指定输出路径：

```bash
python3 scripts/build.py path/to/meet.md -o path/to/output.html
```

从 stdin：

```bash
python3 scripts/build.py -o /tmp/meet.html <<'EOF'
# 面试问题

## 张三 - 2026-07-08 10:30
1. （开场·简介）预设问题1 ...
2. （项目复盘·问题解决）预设问题2 ...
EOF
```

排查解析结果（不写文件，只打印 JSON）：

```bash
python3 scripts/build.py path/to/meet.md --print-json
```

## 输入格式（仅 Markdown）

### 正文写法

```markdown
# 面试问题

## 小王 - 2026-07-08 10:30:00
1. （项目复盘·问题解决）你项目遇到过什么bug……
2. （技术权衡·分析能力）你这个项目，选择3个你认为最核心的技术，并说出原因……
3. （协作·沟通）这个项目很成熟是自己做的么……
```

### 规则

- `# {主标题}`：可选，缺省为“面试问题与记录”
- `## {候选人} - {时间}`：候选人用 `-` / `–` / `—` 与时间分隔；秒可省，脚本自动去秒
- `数字. （标签1·标签2）问题正文`：编号决定顺序；标签括号支持中英文，多个标签用 `·` / `、` / `,` / `/` / `|` 分隔
- 标签可省略：`3. 直接写问题` 也合法
- 问题正文不做 Markdown 渲染，原样展示

## 底部按钮

- **直接打印**：打印时按钮自动隐藏，每题卡片有边框、不被分页切断；打印对话框请取消“页眉和页脚”勾选，页脚会居中显示页码
- **导出为 Markdown**：把所有问题与已填写的总结导出为 .md 文件，临时添加的问题也会包含

## Agent 注意

- 用户给的是自然语言面试清单时，先转成合规 Markdown 再跑脚本
- 输出路径由用户指定；未指定则用 `输入名.html` 同目录，stdin 时落到 `/tmp/meet.html`
- 需要微调视觉时改 `assets/template.html`，并同步更新脚本占位符

