---
name: weather-search
description: 按地点与活动半径查周边天气与空气质量，输出 Markdown 报告与出门防护建议。用户提及「周边天气」「天气咋样」「出门建议」时使用。
version: 1.0.0
dependencies:
  - "python>=3.10"
  - esflow
  - openmeteo-requests
  - pandas
repository: https://github.com/gitByEOS/open-part-skills
---

# 天气面状查询

输入**城市或地点** + **活动半径(km)** + **天数**，自动完成：

1. 地理编码定位中心点
2. 中心 + 8 方向共 9 点拉取预报与空气质量
3. 按本地日期聚合极端要素，生成 Markdown 报告
4. Agent 写出门防护建议

## 依赖

```bash
pip install esflow openmeteo-requests pandas
```

## 使用

```bash
# 1. 首跑到 agent_advice 退出(exit 2)
python3 scripts/run.py --query 北京天安门
python3 scripts/run.py --query 北京大兴机场 --days 3 --radius-km 10 [--out ./out]
# stdout: envelope JSON(ok, data.job_dir / analyze_grid_artifact / advice_path)
# stderr: [to_agent] 续跑命令 + [样式] 表格约束

# 2. Agent 读 analyze_grid_artifact,写 data.advice_path

# 3. 续跑落盘
python3 scripts/run.py --resume <job_dir>
# stdout: envelope(ok, data.out_path / data.out_dir / data.job_dir)
```

最终报告路径为 envelope `data.out_path`。未传 `--out` 时写到 `export/weather_report.md`；传 `--out <DIR>` 时写到 `<DIR>/weather_report.md`，`--resume` 会自动继承首跑入参。

## 参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--query` | - | 城市或具体地点（首跑必填） |
| `--days` | `1` | 预报天数 |
| `--radius-km` | `5` | 活动半径 km |
| `--out <DIR>` | - | 最终报告输出目录 |
| `--resume <job_dir>` | - | 续跑 TO_AGENT 节点 |
| `--schema` | false | 输出 stdout JSON 契约 |

退出码：`0 ok / 1 runtime / 2 to_agent / 3 validation`。esflow 事件走 stderr，不污染 stdout envelope。

## 节点(8 个)

| id | depth | 职责 |
|---|---|---|
| `parse_args` | 0 | query + radius_km + days |
| `geocode` | 1 | Nominatim 编码 |
| `build_grid` | 2 | 中心 + 8 方向采样点列表 |
| `fetch_bulk` | 3 | 两点坐标 bulk:forecast + air-quality,本地日聚合 |
| `analyze_grid` | 4 | 极值定位、`llm_text` / `llm_json` |
| `format_table` | 5 | Markdown 报告 + 独立 LLM 输入 |
| `agent_advice` | 6 | TO_AGENT,写 `advice.md` |
| `export` | 7 | 合并落盘 |

## DAG

```
parse_args → geocode → build_grid → fetch_bulk → analyze_grid → format_table
                                                              ↓
                       export ← agent_advice(TO_AGENT)
```

## TO_AGENT

1. 首跑在 `agent_advice` 以 exit 2 暂停；解析 **stdout** 一行 envelope，`data` 含 `job_dir`、`analyze_grid_artifact`、`advice_path`
2. 读 **`{job_dir}/.esflow/analyze_grid/artifact.json`**：优先 **`llm_text`**（告警段优先），或结构化 **`llm_json`**（`alerts`、`points_merged`、`daily_reports` 等）；勿依赖 stderr 里嵌的上游 markdown
3. 按下列样式写到 **`agent_advice/advice.md`**（即 `data.advice_path`），勿复述报告表格已有数值
4. `python3 scripts/run.py --resume <job_dir>` 续跑 export

**出门建议样式（与 stderr `[样式]` 一致）**

- 标题：`## 外出建议`
- 表头固定：`日期 | 风险点 | 外出建议`
- 风险点用短语，行动一句话；可合并连续同类日期（如 `07-10 至 07-11`）
- 不写表格外总结

## 技术选型

- Open-Meteo forecast + air-quality,`openmeteo-requests` 批量坐标
- `pandas` 做 hourly→日聚合与典型时刻(8/12/16/20)
- 无本地响应缓存(个人使用)
- Nominatim 仍用标准库预检

## 预检

- Python >= 3.10
- Nominatim 可达
