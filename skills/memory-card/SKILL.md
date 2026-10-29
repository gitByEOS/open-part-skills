---
name: memory-card
description: 把课文拆成记忆卡并导出钉纸地图，点节点进入可左右滑动的叠卡，底部弹出串联和原文。用户提到记忆卡、背诵课文、课文背诵、串联点时使用。
version: 1.0.0
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# memory-card

把课文写成记忆卡 JSON，导出单文件网页：钉纸地图看全貌，点节点进叠卡，逐卡背串联和原文。

## 用法

```bash
python3 <skill>/scripts/cards2html.py <输入.cards.json> [-o 输出.html]
```

- 默认输出到源文件同目录，已存在会覆盖；仅依赖 Python 标准库，产物双击即开
- 校验失败会指出第几张、违反哪条规则；改 JSON 重跑，直到退出码为 0
- 脚本只校验和导出，不替你抽取锚点

## 写 JSON

格式参考 [references/sample.cards.json](references/sample.cards.json)。根上的 `title` 是课文名，`cards` 按原文自然段一段一张，不自行合并或切分，每卡四个字段：

| 字段 | 规则 |
|---|---|
| `title` | `段落一 · 乌云先至`：中文数字序、空格、间隔号、空格、2–8 字主题；序号必须对上卡片顺序，只支持到九十九 |
| `desc` | 本段名词，顿号连接；从 `point` 的锚点里挑，每项是某个锚点的连续子串，不要动词短语 |
| `point` | 段落的骨架：用尽量少的「名词-动词」锚点概述整段，看到锚点能回忆原文；锚点按原文顺序排列、含汉字、至多 4 字，其余用点串分隔；点串 3–6 个点，只作分隔，不表示被删字数 |
| `full` | 该段原文，不改写 |

锚点必须按顺序、不重叠地出现在 `full` 里。角标 `01` 由脚本生成，不要写进 `title`。

`point` 的取舍看示例：`乌云、压下来、叶子、不动、蝉、声、不出` 七个词撑起整段，省掉的全是修饰和连接；不是逐句摘词，而是能复述原文的最少骨架。

