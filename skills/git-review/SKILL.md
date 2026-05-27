---
name: git-review
version: 1.0.0
description: 审查指定范围内的 Git 提交，按作者和 commit 汇总风险，输出过程记录与可视化安全审查报告。当用户需要审查 Git 提交风险或生成安全审查报告时使用
license: MIT
repository: https://github.com/gitByEOS/open-part-skills
---

# Git Review

## 如何工作

- 抓取指定时间范围或分支范围内的 Git 提交
- 逐个 commit 审查代码风险、敏感信息、危险操作和可疑变更
- 生成 `process.md`，记录审查过程、作者风险榜和 Commit 风险明细
- 生成 `security_report.html`，方便浏览器查看和分享审查结果
- 所有运行产物写入 `/tmp/reports/git-review-YYYYMMDD-HHMM/`

## 资产文件

- `assets/vigil.md`：角色设定和四步审查流程，执行前必须读取
- `assets/vigil_report.py`：固定 HTML 样式生成脚本，第四步必须调用

## 执行流程

1. 读取 `assets/vigil.md`，按其中角色和审查规则执行
2. 创建输出目录 `/tmp/reports/git-review-YYYYMMDD-HHMM/`
3. 抓取指定时间范围 git 日志，写入该目录下的 `process.md`
4. 审查每个 commit 的代码风险，补全 `process.md`
5. 生成双索引聚合。
  - `A. 作者风险榜`
  - `B. Commit 风险明细`
6. 调用 `assets/vigil_report.py` 生成网页到同一输出目录

## vigil_report.py说明

默认输出到 `process.md` 同目录, `process.md` 必须位于 `/tmp/reports/git-review-YYYYMMDD-HHMM/`：

```bash
python3 {skill}/assets/vigil_report.py /tmp/reports/git-review-YYYYMMDD-HHMM/process.md
```

## 硬性规则

- `security_report.html` 必须由 `assets/vigil_report.py` 生成，避免样式漂移
- 审查代码只读，不修改被审查业务代码
- 每次审查使用独立目录 `/tmp/reports/git-review-YYYYMMDD-HHMM/`，避免覆盖历史报告

