---
name: holiday-of-12306
description: 12306 节假日抢票日历。输入出发站与返程站,自动同步 chinesecalendar、分别查两站起售时间,生成 HTML 页,一键下载 ICS 导入日历。用户提及「节假日购票」「12306 起售时间」时使用本 skill。
version: 1.1.0
dependencies:
  - python3
  - requests
  - chinesecalendar
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# 12306 节假日抢票日历

输入**出发站**与**返程站**(返程可省略),自动完成:

1. 从 12306 官方接口获取全国车站代码,模糊匹配站名(支持常见错字)
2. 分别查询出发站、返程站的起售时间
3. 用 **chinesecalendar** 识别指定年份各法定节假日的放假区间
4. 打开 HTML 抢票日历页:去程按**假期首日**乘车,返程按**假期末日**乘车

## 依赖

Python 包:

```bash
pip install esflow requests chinesecalendar
```

## 快速使用

```bash
# 去程 + 返程
python3 scripts/run.py 北京南 天津西 2026

# 仅去程(第二参数直接写年份)
python3 scripts/run.py 北京南 2026

# 同步节假日库并自检,不生成日历
python3 scripts/run.py --update
```

**默认行为**:写入 `~/Downloads/ticket-calendar/ticket-calendar-{出发站}-{返程站}-{年}.html`(仅去程时无返程站名),并自动打开浏览器。在服务器/容器/headless 环境请加 `--out <dir>` + `--no-open` 避免污染家目录或卡在弹窗。

## 产物形态

- **HTML**:自包含单文件,内嵌抢票条目数据与 ICS/CSV 生成逻辑(浏览器端 JS 动态拼装)
- **ICS / CSV**:**无独立文件产物**,在浏览器打开 HTML 后点「下载 ICS / CSV」按钮生成;headless 环境无法获取,需有浏览器

## Flow 结构

esflow DAG 编排(`scripts/flow.py` 声明,`scripts/nodes/` 各节点):

```text
holidays ∥ resolve_stations → query_sale_time → export_html
```

- `holidays`:入口节点,升级 chinesecalendar + 取目标年份节假日区间,与 resolve_stations **并行**
- `resolve_stations`:入口节点,下载站名表 + 模糊匹配出发/返程站
- `query_sale_time`:依赖 resolve_stations,查去程 + 返程起售时间(无返程站则返程字段 None)
- `export_html`:**扇入** holidays 与 query_sale_time,组装抢票条目 + 生成 HTML + 弹出浏览器

无 TO_AGENT 断点,纯数据流一次跑完。无返程站时 `query_sale_time` 返程字段返回 None,`export_html` 不生成返程条目。

## 操作 SOP(对应四节点)

### resolve_stations:解析车站 → 电报码

1. 下载 `https://kyfw.12306.cn/otn/resources/js/framework/station_name.js`
2. 提取 `站名|代码` 映射
3. 模糊匹配出发站、返程站:精确命中优先;否则按相似度 + 同长度前缀加分
   例:`北京难` → `北京南`
4. 匹配失败抛 `station_error` 列出候选(esflow 非交互,不再 stdin 询问)

### query_sale_time:查询起售时间

分别查出发站、返程站:

1. 优先调用官方缓存接口 `queryAllCacheSaleTime`,按 `station_telecode` 查 `sale_time`
2. 失败时回退解析 `sale_time.html` 页面
3. 仍失败则默认 `14:00` 并标注

### holidays:获取节假日(chinesecalendar)

- 遍历指定年份每一天,用 `get_holiday_detail` 识别节日名
- 取每个节日**首日**(去程乘车日)与**末日**(返程乘车日)
- 支持跨年查询;年份超库支持范围抛 `holiday_error`

### export_html:打开 HTML 日历页

写入 `~/Downloads/ticket-calendar/`,并自动打开浏览器。网页内完成:

- **出发 / 返程**切换(默认出发),表格与导出仅含当前行程
- 提醒方式:当天 / 提前 1 / 2 / 3 天(默认当天);起售前分钟数可调(默认 15)
- 每行可**忽略**不出行的节日(如端午),导出时不包含,可恢复
- 下载 ICS 或 CSV,内容与当前选项一致

| 方向 | 乘车日 | 抢票日 | 起售站 |
|------|--------|--------|--------|
| 去程 | 假期首日 | 首日 − 15 天 | 出发站 |
| 返程 | 假期末日 | 末日 − 15 天 | 返程站 |

预售期 15 天,以 12306 官方为准。

## 参数

| 参数 | 说明 |
|---|---|
| `departure` | 出发站名,如 北京南 |
| `return_station` | 返程站名,如 天津西;省略则仅生成去程 |
| `year` | 目标年份,默认当前年 |
| `--update` | 仅升级 chinesecalendar 并自检,不生成日历 |
| `--skip-update` | 跳过默认的节假日库同步 |
| `--out <dir>` | HTML 输出目录,默认 `~/Downloads/ticket-calendar`(headless 环境建议显式指定) |
| `--no-open` | 不自动打开浏览器(headless 环境必加) |
| `--job-dir <dir>` | 指定 esflow job 目录 |
| `--schema` | 仅打印 JSON 契约到 stdout 后退出,不跑 flow、不生成产物(退出码 0) |

退出码:`0 ok / 1 runtime / 3 validation`

## 输出契约

成功时 stdout 输出一行 JSON envelope:

```json
{
  "ok": true,
  "data": {
    "html_path": "/path/to/ticket-calendar-北京南-天津西-2026.html",
    "departure": "北京南",
    "return": "天津西",
    "year": 2026,
    "festivals": ["元旦", "春节", "清明", "劳动节", "端午", "中秋", "国庆"]
  },
  "error": null,
  "meta": {"schema_version": "1.0.0", "tool": "holiday-of-12306", "elapsed_ms": 1489}
}
```

失败时 `ok=false`,`error` 含 `{code, message, retryable}`;`data` 为 null。`--schema` 输出同结构但字段为类型说明字符串。esflow 事件流(trace/running/artifact)走 stderr,不污染 stdout 的 envelope。

## 异常处理

| 情况 | 行为 |
|------|------|
| 车站匹配失败 | 抛 `station_error`,列出候选站名 |
| 起售时间查询失败 | 日志输出失败原因,回落 `14:00 (默认)`(接口正常返回 14:00 时无「(默认)」后缀,可区分) |
| 节假日数据缺失 | 抛 `holiday_error`,执行 `--update` 查看详情 |
| 年份超库支持范围 | 抛 `holiday_error`,提示支持区间 |

## Agent 使用指引

用户提到「抢票日历」「节假日购票」「12306 起售时间」时使用本 skill:

1. 确认出发站、返程站(可选)、目标年份
2. 执行 `python3 scripts/run.py <出发站> [返程站] [年份]`
3. 引导用户在网页中切换出发/返程、忽略不出行的节日、选择提醒后下载 ICS
