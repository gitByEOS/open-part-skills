---
name: okr-to-html
description: 将 OKR Markdown 生成为可切换 Objective 的单页 HTML 看板。用户提到 okr-to-html、OKR 转网页、季度目标 HTML 时使用。
version: 1.0.0
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# OKR to HTML

把结构化 OKR Markdown 导出为交互式 HTML（底部 Tab 切换 O1/O2/O3，样式以 `assets/template.html` 为准）。

## 工作流

1. 按下方**输入格式**整理用户的文本或 Markdown（可写入临时 `.md`）
2. 执行生成脚本并指定输出路径：

```bash
python3 scripts/build.py path/to/okr.md -o path/to/output.html
```

3. 用浏览器打开输出 HTML；校验 O 与 KR 权重是否齐全
4. **不要**手改 `assets/template.html` 里的样式逻辑凑数据；内容只走输入文件

从 stdin：

```bash
python3 scripts/build.py -o /tmp/okr.html <<'EOF'
...
EOF
```

参考样例：`references/demo.md`（1~7 条 KR 兼容性压测）。

## 输入格式（仅 Markdown）

### 可选 YAML 头

| 字段 | 含义 |
|------|------|
| `title` | `<title>` 与默认页名 |
| `heading` | 主标题（配合 `accent` 高亮一词） |
| `accent` | 在 heading 中包裹 `<span class="accent">` |
| `subtitle` | 副标题 |

无 frontmatter 时可用 `# 主标题` 与 `> 副标题` 替代。

### Objective 写法

```markdown
---
title: OKR 兼容 Demo | O1–O3
heading: 团队成长 OKR 演示
accent: OKR
subtitle: 1~3 条 KR 写法示例
---

## O1 · 专注
季度只做一件事，做到极致

- **核心产品**月活突破 **50 万** | 100%

## O2 · 健康
守护团队可持续的节奏

- 关键服务 **99.9%** 可用 | 60%
- 人均加班时长低于 **10 小时/月** | 40%

## O3 · 招聘
补齐关键岗位的人才缺口

- 资深前端到岗 **2 人** | 40%
- 算法工程师到岗 **1 人** | 35%
- 实习生转正率 **≥ 60%** | 25%
```

### 规则

- `## O{n} · {底部 Tab 文案}`，分隔符支持 `·` / `.` / `-`
- 标题下**首行非列表** = 卡片上的 O 描述（单行）
- 每条 KR 以 `- ` 开头，行末 `| 40%` 或 `| 权重 40%`
- KR 文本支持 `**粗体**`
- 每个 O 必须有描述和至少一条 KR
- 所有 KR 权重之和建议 100%（脚本不强制）

## 输出约定

- 单文件 HTML，无外部依赖
- 首张卡片默认激活；键盘 `1`~`9` 与方向键切换
- 样式、布局、权重铭牌以模板为准；**仅替换**标题、副标题、卡片与 Tab 文案

## 故障排查

| 现象 | 处理 |
|------|------|
| `KR 行缺少权重` | 每行末尾补 `\| NN%` |
| `未解析到任何 Objective` | 检查 `## O1 ·` 格式 |
| `O{n} 缺少目标描述` | 标题下加一行目标说明 |
| 生成后样式不对 | 对比 `assets/template.html` 是否被误改 |

## Agent 注意

- 用户给的是自然语言 OKR 时，先转成合规 Markdown 再跑脚本
- 输出路径由用户指定；未指定则用 `输入名.html` 同目录
- 需要微调视觉时改 `assets/template.html`，并同步更新 `references/demo.md` 与脚本占位符
