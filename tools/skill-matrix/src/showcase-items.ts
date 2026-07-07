import type { ShowcaseItem } from "./types";

const repo = "https://github.com/gitByEOS/open-part-skills";
const rawMain = "https://raw.githubusercontent.com/gitByEOS/open-part-skills/main";

function skill(
  id: string,
  name: string,
  folder: string,
  shortIntro: string,
  icon: string,
  tag?: ShowcaseItem["tag"],
): ShowcaseItem {
  const installCommand = `npx skills add ${repo} --skill ${folder}`;
  return {
    id,
    type: "skill",
    name,
    shortIntro,
    documentUrl: `${rawMain}/skills/${folder}/SKILL.md`,
    displayCommand: installCommand,
    installCommand,
    icon,
    tag,
  };
}

function mcp(
  id: string,
  name: string,
  slug: string,
  shortIntro: string,
  icon: string,
): ShowcaseItem {
  const repoUrl = `https://github.com/gitByEOS/${slug}`;
  return {
    id,
    type: "mcp",
    name,
    shortIntro,
    documentUrl: "",
    githubRepo: `gitByEOS/${slug}`,
    displayCommand: repoUrl,
    installCommand: repoUrl,
    icon,
  };
}

function sortSkills(items: ShowcaseItem[]) {
  const hot = items.filter((item) => item.tag === "hot");
  const rest = items.filter((item) => item.tag !== "hot");
  const byName = (left: ShowcaseItem, right: ShowcaseItem) =>
    left.name.localeCompare(right.name, "en", { sensitivity: "base" });
  hot.sort(byName);
  rest.sort(byName);
  return [...hot, ...rest];
}

const skills = sortSkills([
  skill(
    "skill-webfetch-plus",
    "WebFetch Plus",
    "webfetch-plus",
    "使用 Browser 抓取普通 WebFetch 失败的网页内容，并输出适合大模型阅读的正文文本。",
    "抓",
    "hot",
  ),
  skill(
    "skill-switch-chat",
    "Switch Chat",
    "switch-chat",
    "切换会话并交接任务，生成可视化交接文档，新会话可无缝继续工作。",
    "切",
    "hot",
  ),
  skill(
    "skill-blog-narrator",
    "Blog Narrator",
    "blog-narrator",
    "博客 Markdown 导出为逐行披露演示 HTML，支持 Edge TTS 分段配音。",
    "讲",
  ),
  skill(
    "skill-cc-claude",
    "CC Claude",
    "cc-claude",
    "自定义 Anthropic 兼容渠道的 Claude Code（已迁移至 Clash 仓库，skill 仍保留说明）。",
    "渠",
  ),
  skill(
    "skill-fetch-what-say",
    "Fetch What Say",
    "fetch-what-say",
    "抓取 yt-dlp 支持的媒体或本地视频，转写文字稿并生成树形思维导图摘要。",
    "听",
  ),
  skill(
    "skill-git-review",
    "Git Review",
    "git-review",
    "审查指定范围内 Git 提交风险，按作者与 commit 汇总，并生成可视化报告。",
    "审",
  ),
  skill(
    "skill-holiday-of-12306",
    "Holiday Of 12306",
    "holiday-of-12306",
    "12306 节假日抢票日历：查起售时间并生成 ICS 导入日历。",
    "票",
  ),
  skill("skill-juya", "Juya", "juya", "获取橘鸦 Juya AI 早报，生成早茶风格排版 HTML。", "橘"),
  skill(
    "skill-memory-graph",
    "Memory Graph",
    "memory-graph",
    "Agent 外挂记忆图谱：link 关联历史、patch 沉淀记忆、apply 写入、look 管理。",
    "忆",
  ),
  skill(
    "skill-mock-ollama",
    "Mock Ollama",
    "mock-ollama",
    "模拟 Ollama API 代理真实 LLM，监控请求响应并提供 Dashboard。",
    "模",
  ),
  skill(
    "skill-okr-to-html",
    "OKR to HTML",
    "okr-to-html",
    "将 OKR Markdown 生成为可切换 Objective 的单页 HTML 看板。",
    "讲",
    "new",
  ),
  skill(
    "skill-meet-record-html",
    "Meet Record HTML",
    "meet-record-html",
    "将面试/会谈问题 Markdown 生成为可现场填写总结、可临时追加问题的纪要 HTML。",
    "纪",
    "new",
  ),
  skill(
    "skill-similar-judge",
    "Similar Judge",
    "similar-judge",
    "对比两份文本差异，输出相似度与词级差异 JSON，便于循环迭代提示词。",
    "似",
  ),
  skill(
    "skill-skill-linker",
    "Skill Linker",
    "skill-linker",
    "通过 fzf 搜索、多选并软链本地 skills/rules，多项目 skill 体系切换。",
    "链",
  ),
  skill(
    "skill-publish-verify",
    "Skill Publish Verify",
    "skill-publish-verify",
    "发布前黑盒验证：隔离 venv + 路径，agent 以新用户身份自验任意 skill，产出可用性报告。",
    "验",
    "new",
  ),
  skill("skill-testcase", "Testcase", "testcase", "按规则补全测试用例覆盖，提升完整性与有效性。", "测"),
  skill(
    "skill-vite-plus",
    "Vite Plus",
    "vite-plus",
    "适合 Agent 的 Web 前端工具链：vp 开发/构建/测试/发布一体化。",
    "架",
  ),
  skill(
    "skill-voice-clone",
    "Voice Clone",
    "voice-clone",
    "Confucius4-TTS Gradio API 参考音色克隆与文本转语音。",
    "声",
  ),
]);

const mcps: ShowcaseItem[] = [
  mcp(
    "mcp-agents-chat",
    "Agents Chat MCP",
    "agents-chat-mcp",
    "把 Agent 接入聊天室，实现跨设备、跨项目协作的最小架构。",
    "聊",
  ),
  mcp(
    "mcp-lark-chat",
    "Lark Chat MCP",
    "lark-chat-mcp",
    "以飞书做桥，通过手机指挥 Claude / Cursor 等 Agent。",
    "控",
  ),
];

/** 与仓库 README 同步：仅 open-part-skills 开源 skill 与关联 MCP */
export const showcaseItems: ShowcaseItem[] = [...skills, ...mcps];
