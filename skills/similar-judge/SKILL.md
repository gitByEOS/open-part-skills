---
name: similar-judge
description: 对比两份文本差异，输出相似度与词级差异 JSON。当 agent 需要量化产物与目标的文本差距时使用
version: 1.0.0
dependencies:
  - git
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# Similar Judge

量化两份文本的差异。输入产物与目标，输出 JSON：相似度 + 词级差异原文。

**只量差异，不评质量**。相似度高不等于内容正确（可能因果倒置、数量级错误），质量判断交给上层 LLM。

## 调用

```bash
# 默认输出 JSON
{skill}/bin/similar-judge 产物.txt 目标.txt

# 调试模式（人类可读）
{skill}/bin/similar-judge 产物.txt 目标.txt --text
```

参数顺序固定：**先产物，后目标**。目标为基准。默认忽略空白差异（git `-w` 口径）。

## JSON 字段

```json
{
  "line_sim_ratio": 0.5,
  "word_sim_ratio": 0.8103,
  "target_lines": 20,
  "product_lines": 20,
  "added_lines": 10,
  "deleted_lines": 10,
  "diff_chars": 386,
  "diff": "# 用户中心\n[-用户中心提供登录注册功能。-]{+用户中心负责身份认证与会话管理。+}\n..."
}
```

| 字段 | 含义 |
|------|------|
| `line_sim_ratio` | 行级相似度，对行顺序错位敏感 |
| `word_sim_ratio` | 词级相似度，跟人眼感受一致，**推荐主指标** |
| `target_lines` / `product_lines` | 两侧行数 |
| `added_lines` / `deleted_lines` | 产物冗余 / 产物遗漏的行数 |
| `diff_chars` | `diff` 字段字符长度，供 LLM 预判体量 |
| `diff` | git word-diff 内容，含 `[-old-]{+new+}` 词级标记 |

## 边界

**能做**：相似度计算、增删行数统计、词级差异原文输出

**不做**：质量评判、事实核查、优化建议、闭环决策，交给 LLM

## 硬性规则

- 默认输出 JSON，`--text` 仅调试用
- `diff` 字段剥掉 git 元数据 header，只留 word-diff 内容
- 不输出评判语义文案（"质量高/低"等），避免误导上层
- 不修改产物与目标，只读
