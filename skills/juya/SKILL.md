---
name: juya
description: 获取橘鸦Juya的AI早报，用户提到橘鸦、AI早报、Juya时使用。
version: 1.0.2
dependencies:
  - webfetch-plus
repository: https://github.com/gitByEOS/open-part-skills
---

# 橘鸦Juya AI早报

获取橘鸦Juya每日更新的AI早报，输出早茶风格 HTML 供人类阅读。

## 执行原则

- 获取当前时间判断早报日期：`date "+%Y-%m-%d %H:%M:%S"`
- 早报通常在每日 09:00 左右发布，可根据时间判断最新日期
- 把当前 skill 路径设置给 `WFP_PATH`，指向 webfetch-plus 所在目录
- 任何 webfetch-plus 命令执行，必须先 `cd "$WFP_PATH"`

## 获取方式（仅三种，按优先级）


| 优先级      | 方式    | 脚本 / 工具                            | webfetch 次数 | 说明                           |
| -------- | ----- | ---------------------------------- | ----------- | ---------------------------- |
| **1 首选** | RSS   | `rss-to-html.py`                   | 0           | HTTP 拉 RSS，排版最佳              |
| **2 备选** | 微信公众号 | `wx-to-html.py`                    | 1～2         | RSS 失效时使用，正文转 RSS item 后统一渲染 |
| **3 兜底** | B站合集  | webfetch-plus → `wx-to-html.py -u` | 2～3         | 从视频简介提取微信链接，再导出 HTML         |


## 执行流程

```text
用户请求早报 →
  ① RSS 脚本（rss-to-html.py）
      ↓ 失败 / 无当日条目
  ② 微信脚本（wx-to-html.py）
      ↓ 失败
  ③ B站合集取最新视频简介中的微信链接 → wx-to-html.py -u <链接>
      ↓
  输出 juya-YYYY-MM-DD.html → 打开浏览器
```

---

## 方式一：RSS（首选）

```bash
python3 <skill-path>/scripts/rss-to-html.py [输出目录]
python3 <skill-path>/scripts/rss-to-html.py [输出目录] -d 2026-06-09
```

- RSS 源：`https://daily.juya.uk/rss.xml`
- 输出：`juya-YYYY-MM-DD.html`
- 无需 webfetch-plus，无需 stealth

---

## 方式二：微信公众号（备选）

RSS 不可用或缺少当日条目时使用。流程：定位文章 → 抽取正文 → 转为 RSS item → 调用与方式一相同的渲染管线。

```bash
python3 <skill-path>/scripts/wx-to-html.py [输出目录]
python3 <skill-path>/scripts/wx-to-html.py [输出目录] -d 2026-06-09
```

**减少 webfetch 调用（按顺序尝试）：**


| 场景                 | 命令                                   | webfetch 次数 |
| ------------------ | ------------------------------------ | ----------- |
| 已有微信文章链接           | `wx-to-html.py [目录] -u '<微信链接>'`     | **1**       |
| 同日重复执行 / 缓存未过期（6h） | 直接跑脚本                                | **1**       |
| 脚本内 RSS 能解析到微信链接   | 自动跳过专辑                               | **1**       |
| 首次或需刷新专辑索引         | `wx-to-html.py [目录] --refresh-album` | **2**       |


常用参数：

```bash
--url / -u          微信文章直链，跳过专辑抓取
--date / -d         指定日期 YYYY-MM-DD（默认最新一期）
--refresh-album     忽略 RSS/缓存，强制重抓专辑
--no-open           生成后不自动打开浏览器
```

脚本结束会打印 `webfetch 调用次数: N`。

**公众号专辑（脚本内部使用）：**

- `__biz`: `MzIyMDk0MDY1OA==`
- `album_id`: `4066755324999598083`

---

## 方式三：B站合集（兜底）

微信脚本也失败时，从 B 站 AI 早报合集最新视频简介获取微信链接，再用 `-u` 只抓正文。

**Step 1** — 打开合集，找到最新视频 BV 号：

```bash
cd "$WFP_PATH"
echo "https://space.bilibili.com/285286947/channel/collectiondetail?sid=572036 --wait 3000" | bash bin/wfp.sh
```

**Step 2** — 抓取视频页，从简介提取微信链接：

```bash
echo "https://www.bilibili.com/video/<BV号> --wait 3000" | bash bin/wfp.sh
```

简介格式示例：`相关链接和文字版请看：https://mp.weixin.qq.com/s/xxxxx`

**Step 3** — 用直链导出 HTML（仅 1 次 webfetch）：

```bash
python3 <skill-path>/scripts/wx-to-html.py [输出目录] -u 'https://mp.weixin.qq.com/s/xxxxx'
```

---

## 失败处理

1. 读取 webfetch-plus 输出的 `attempt_{n}_{N}.metadata.json` 中 `suggestion` 字段
2. 按建议调整参数重试（微信页面通常需要 `--stealth`，脚本已内置）
3. 同一层级最多重试 3 次，再降级到下一优先级方式

## 输出格式

早报 HTML 包含以下板块：

- **概览要闻**：当日重点新闻
- **模型发布**：新模型发布信息
- **开发生态**：开发工具、API 更新
- **产品应用**：产品新功能
- **技术与洞察**：技术分析、安全报告
- **行业动态**：政策、融资、行业新闻
- **前瞻与传闻**：未来规划和传闻

每条新闻有编号（#1-#N），包含标题、详细描述和原文链接。