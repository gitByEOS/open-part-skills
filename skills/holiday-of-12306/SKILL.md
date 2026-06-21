---
name: holiday-of-12306
description: 12306 节假日抢票日历。输入出发站与返程站，自动同步 chinesecalendar、分别查两站起售时间，生成 HTML 页，一键下载 ICS 导入日历。用户提及「节假日购票」「12306 起售时间」时使用本 skill。
version: 1.0.0
dependencies:
  - python3
  - requests
  - chinesecalendar
repository: https://github.com/gitByEOS/open-part-skills
---

# 12306 节假日抢票日历

输入**出发站**与**返程站**（返程可省略），自动完成：

1. 从 12306 官方接口获取全国车站代码，模糊匹配站名（支持常见错字）
2. 分别查询出发站、返程站的起售时间
3. 用 **chinesecalendar** 识别指定年份各法定节假日的放假区间
4. 打开 HTML 抢票日历页：去程按**假期首日**乘车，返程按**假期末日**乘车

## 快速使用

```bash
# 首次安装依赖
pip install requests chinesecalendar

# 去程 + 返程
python3 scripts/ticket_calendar.py 北京南 天津西 2026

# 仅去程（第二参数直接写年份）
python3 scripts/ticket_calendar.py 北京南 2026
```

## 操作 SOP

### 第一步：解析车站 → 电报码

1. 下载 `https://kyfw.12306.cn/otn/resources/js/framework/station_name.js`
2. 提取 `站名|代码` 映射
3. 模糊匹配出发站、返程站：精确命中优先；否则按相似度 + 同长度前缀加分  
   例：`北京难` → `北京南`

### 第二步：查询起售时间

分别查出发站、返程站：

1. 优先调用官方缓存接口 `queryAllCacheSaleTime`，按 `station_telecode` 查 `sale_time`
2. 失败时回退解析 `sale_time.html` 页面
3. 仍失败则默认 `14:00` 并标注

### 第三步：获取节假日（chinesecalendar）

- 遍历指定年份每一天，用 `get_holiday_detail` 识别节日名
- 取每个节日**首日**（去程乘车日）与**末日**（返程乘车日）
- 支持跨年查询

### 第四步：打开 HTML 日历页

写入 `~/Downloads/ticket-calendar/ticket-calendar-{出发站}-{返程站}-{年}.html`（仅去程时无返程站名），并**自动打开浏览器**。

网页内完成：

- **出发 / 返程**切换（默认出发），表格与导出仅含当前行程
- 提醒方式：当天 / 提前 1 / 2 / 3 天（默认当天）；起售前分钟数可调（默认 15）
- 每行可**忽略**不出行的节日（如端午），导出时不包含，可恢复
- 下载 ICS 或 CSV，内容与当前选项一致

| 方向 | 乘车日 | 抢票日 | 起售站 |
|------|--------|--------|--------|
| 去程 | 假期首日 | 首日 − 15 天 | 出发站 |
| 返程 | 假期末日 | 末日 − 15 天 | 返程站 |

预售期 15 天，以 12306 官方为准。


## 异常处理

| 情况 | 行为 |
|------|------|
| 车站匹配失败 | 列出候选站名，提示用户重新输入 |
| 起售时间获取失败 | 使用 `14:00 (默认)` |
| 节假日数据缺失 | 重试；或执行 `--update` 查看详情 |

## Agent 使用指引

用户提到「抢票日历」「节假日购票」「12306 起售时间」时使用本 skill：

1. 确认出发站、返程站（可选）、目标年份
2. 执行 `python3 scripts/ticket_calendar.py <出发站> [返程站] [年份]`
3. 引导用户在网页中切换出发/返程、忽略不出行的节日、选择提醒后下载 ICS
