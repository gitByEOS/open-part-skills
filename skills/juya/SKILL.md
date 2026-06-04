---
name: juya
description: 获取橘鸦Juya的AI早报，用户提到橘鸦、AI早报、Juya时使用。
version: 1.0.0
dependencies:
  - webfetch-plus
repository: https://github.com/gitByEOS/open-part-skills
---

# 橘鸦Juya AI早报

获取橘鸦Juya每日更新的AI早报内容。

## 执行原则

- 获取当前时间判断早报日期：`date "+%Y-%m-%d %H:%M:%S"`
- 早报通常在每日 09:00 左右发布，可根据时间判断最新日期
- 把当前 skill 路径设置给 `WFP_PATH`，指向 webfetch-plus 所在目录
- 任何 webfetch-plus 命令执行，必须先 `cd "$WFP_PATH"`

## 优先级排序

| 方式 | 排版质量 | 杂讯量 | 需要stealth | 人类阅读 | 推荐 |
|------|---------|--------|------------|---------|------|
| **RSS + 脚本处理** | ★★★★★ | 无 | 否 | **最佳** | **首选** |
| GitHub Pages | ★★★★ | 少 | 否 | 好 | 推荐 |
| RSS原始 | ★★ | 多(元数据) | 否 | 差 | Agent解析用 |
| 微信公众号 | ★★ | 多 | 需要 | 差 | 备用 |

## 方式一：RSS + 脚本处理（首选，人类阅读最佳）

使用脚本解析 RSS，生成早茶风格的 HTML：

```bash
python3 <skill-path>/scripts/rss-to-html.py [输出目录]
```

输出：
- `juya-YYYY-MM-DD.html` - 最新早报，早茶风格排版

打开查看：`open ./juya-output/juya-2026-06-04.html`

## 方式二：GitHub Pages（适合直接阅读）

获取单篇早报完整内容，排版清晰：

```bash
echo "https://imjuya.github.io/juya-ai-daily/issue-<N>/ --wait 2000" | bash "$WFP_PATH/bin/wfp.sh"
```

issue 编号规则：从 RSS 获取，或根据日期推算（如 issue-111 ≈ 2026-06-04）。

## 方式三：RSS订阅（Agent 解析用）

获取原始 RSS 数据，适合程序解析（开头有大量元数据，不适合直接展示）：

```bash
echo "https://imjuya.github.io/juya-ai-daily/rss.xml --wait 2000" | bash "$WFP_PATH/bin/wfp.sh"
```

## 方式四：微信公众号专辑（获取文章列表）

公众号专辑页面包含 439 篇 AI 早报文章列表：

```bash
echo "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzIyMDk0MDY1OA==&action=getalbum&album_id=4066755324999598083 --wait 5000 --stealth" | bash "$WFP_PATH/bin/wfp.sh"
```

专辑页面显示文章标题、发布时间和链接。

**注意**：微信文章排版差（单行压缩），杂讯多（赞赏、留言等），需要 stealth 模式：

```bash
echo "https://mp.weixin.qq.com/s/<id> --wait 3000 --stealth" | bash "$WFP_PATH/bin/wfp.sh"
```

## 方式五：B站最新视频（获取当日微信链接）

从 AI 早报合集的最新视频简介获取微信文章链接：

```bash
echo "https://space.bilibili.com/285286947/channel/collectiondetail?sid=572036 --wait 3000" | bash "$WFP_PATH/bin/wfp.sh"
```

合集页面显示最新视频的 BV 号，然后抓取视频页面提取简介中的微信链接。

视频简介格式：`相关链接和文字版请看：https://mp.weixin.qq.com/s/xxxxx`

## 执行流程

```text
用户请求早报 →
  若要阅读早报 → RSS + 脚本处理（方式一）→ 输出早茶 HTML → 打开浏览器
  若要快速查看 → GitHub Pages（方式二）→ 输出 Markdown
  若要解析数据 → RSS订阅（方式三）→ Agent 提取信息
```

**公众号信息**：
- `__biz`: `MzIyMDk0MDY1OA==`
- `album_id`: `4066755324999598083`
- 专辑链接: `https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzIyMDk0MDY1OA==&action=getalbum&album_id=4066755324999598083`

**成功判定**：stdout 输出 `page_{n}.md` 路径即成功，直接读取。

**失败处理**：
1. 读取 `attempt_{n}_{N}.metadata.json` 的 `suggestion` 字段
2. 根据建议增加参数重试（如微信文章需要 `--stealth`）
3. 最多 3 次重试

## 输出格式

早报包含以下板块：
- **概览要闻**：当日重点新闻
- **模型发布**：新模型发布信息
- **开发生态**：开发工具、API更新
- **产品应用**：产品新功能
- **技术与洞察**：技术分析、安全报告
- **行业动态**：政策、融资、行业新闻
- **前瞻与传闻**：未来规划和传闻

每条新闻有编号（#1-#N），包含标题、详细描述和原文链接。
