# Agent Skills

EOS. 开放的部分 Skills，可用于 Claude Code、Cursor、CodeX 等工具。

AI交流群：**1105239118**，有新内容更新会在里边通知，也可以提一些建议或者想法

## 安装

```bash
npx skills add https://github.com/gitByEOS/open-part-skills --skill <skill-name>
```

## Skills

[![skills.sh](https://skills.sh/b/gitByEOS/open-part-skills)](https://skills.sh/gitByEOS/open-part-skills)

| 技能 | 说明 | 版本 | 上次更新 |
|------|------|------|----------|
| [webfetch-plus](./skills/webfetch-plus/SKILL.md) | 使用 Browser 抓取普通 WebFetch 失败的网页，输出适合大模型阅读的正文文本 | 1.0.3 | 2026-05-19 |
| [testcase](./skills/testcase/SKILL.md) | 通过本skill的规则来完善用户测试用例的完整性和有效性 | 1.0.0 | 2026-05-19 |
| [vite-plus](./skills/vite-plus/SKILL.md) | 最新的适合 Agent 开发 Web 前端工具链，一体化开发/构建/测试/发布/格式化 | 1.0.0 | 2026-05-19 |
| [switch-chat](./skills/switch-chat/SKILL.md) | 切换会话交接任务时使用，生成可快速编辑网页，让新会话能无缝继承工作 | 1.0.0 | 2026-05-19 |
| [git-review](./skills/git-review/SKILL.md) | 审查指定范围内的 Git 提交，按作者和 commit 汇总风险，输出过程记录与可视化安全审查报告 | 1.0.0 | 2026-05-27 |
| [memory-graph](./skills/memory-graph/SKILL.md) | 开发了一套 Agent 外挂记忆，关联历史记忆、沉淀会话记忆、提供 web-ui 查看或管理记忆 | 0.2.1 | 2026-05-29 |
| [blog-narrator](./skills/blog-narrator/SKILL.md) | 把博客 Markdown 导出为带语音逐行披露演示 HTML，支持Edge TTS，可自行拓展其他TTS | 1.0.2 | 2026-05-29 |
| [cc-claude](./skills/cc-claude/SKILL.md) | 让 Claude Code 支持自定义渠道和大模型选择; 已经迁移到 [gitByEOS/Clash](https://github.com/gitByEOS/Clash) | 1.0.0 | 2026-06-01 |
| [skill-linker](./skills/skill-linker/SKILL.md) | 软链[安装/卸载]本地 skill/rule，通过 fzf 支持搜索、多选；用于多项目不同 skill 体系切换，或者不常用技能临时开启 | 1.0.0 | 2026-06-03 |
| [juya](./skills/juya/SKILL.md) | 获取橘鸦Juya每日更新的AI早报内容，生成早茶风格排版的早报 HTML | 1.0.2 | 2026-06-15 |
| [mock-ollama](./skills/mock-ollama/SKILL.md) | 启动 mock-ollama 服务，模拟 Ollama API 代理到真实 LLM，监控请求响应数据并提供 Dashboard | 1.0.0 | 2026-06-09 |

## MCPs

| 服务 | 说明 | 发布日期 | 如何使用 |
|------|------|----------|----------|
| [agents-chat-mcp](https://github.com/gitByEOS/agents-chat-mcp) | 把 Agent 接入聊天室，从而实现跨设备、跨项目协作的最小架构 | 2026-06-10 | [文档](https://github.com/gitByEOS/agents-chat-mcp#readme) |
| [lark-chat-mcp](https://github.com/gitByEOS/lark-chat-mcp) | 以飞书做桥，省去繁项操作，让你可以通过手机指挥你的 Claude/Cursor | 2026-06-14 | [文档](https://github.com/gitByEOS/lark-chat-mcp#readme) |

## 许可

MIT
