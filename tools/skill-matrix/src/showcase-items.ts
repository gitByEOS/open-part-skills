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
    "抓取普通 WebFetch 失败网页，自动复用本地会话，支持隐身抓取与人工验证。",
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
    "skill-bad-solution",
    "Bad Solution",
    "bad-solution",
    "以反思模式审查方案结构性缺陷，给出失败链与最小替代设计。",
    "省",
  ),
  skill(
    "skill-html-cut",
    "HTML Cut",
    "html-cut",
    "将网页或本地 HTML 渲染为高清 PNG 截图，支持全页、视口、分辨率与加载等待控制。",
    "截",
  ),
  skill(
    "skill-port-to-public",
    "Port to Public",
    "port-to-public",
    "临时通过 Cloudflare Quick Tunnel 将本机 loopback HTTP(S) 服务暴露到公网，支持启动、状态、验证与停止。",
    "穿",
  ),
  skill(
    "skill-tmux-serv",
    "tmux-serv",
    "tmux-serv",
    "用全局脚本管理多项目 tmux 常驻服务，用全局脚本管理多项目 tmux 常驻服务，建立统一规范，提高管理效率 。",
    "驻",
    "new",
  ),
  skill(
    "skill-clak",
    "clak",
    "clak",
    "使用 clak 构建固定流程业务脚本，覆盖 TUI、无头 CLI、交互输入与生命周期测试。",
    "控",
  ),
  skill(
    "skill-fetch-what-say",
    "Fetch What Say",
    "fetch-what-say",
    "抓取 yt-dlp 支持的媒体或本地视频，转写文字稿并生成树形思维导图摘要。",
    "听",
  ),
  skill(
    "skill-esflow",
    "esflow",
    "esflow",
    "编排 Python DAG workflow，支持暂停协作、定点续跑、扇出与兜底链。",
    "流",
    "hot",
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
  skill("skill-juya", "Juya", "juya", "获取橘鸦 Juya AI 早报，生成早茶风格排版 HTML。", "报"),
  skill(
    "skill-memory-graph",
    "Memory Graph",
    "memory-graph",
    "Agent 外挂记忆图谱：link 关联历史、patch 沉淀记忆、apply 写入、look 管理；组合关键词优先返回全匹配结果；look 会阻塞终端并提供本地 WebUI。",
    "忆",
  ),
  skill(
    "skill-mock-ollama",
    "Mock Ollama",
    "mock-ollama",
    "代理 Chat、Anthropic、Responses 三协议，支持 Claude、Codex、Cursor。",
    "代",
  ),
  skill(
    "skill-okr-to-html",
    "OKR to HTML",
    "okr-to-html",
    "将 OKR Markdown 生成为可切换 Objective 的单页 HTML 看板。",
    "讲",
  ),
  skill(
    "skill-meet-record-html",
    "Meet Record HTML",
    "meet-record-html",
    "将面试/会谈问题 Markdown 生成为可现场填写总结、可临时追加问题的纪要 HTML。",
    "纪",
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
    "skill-summary-user-said",
    "Summary User Said",
    "summary-user-said",
    "汇总本地 Cursor、Claude Code、Codex 用户发言，生成带证据引用的总结与原文双产物。",
    "述",
  ),
  skill(
    "skill-publish-verify",
    "Skill Publish Verify",
    "skill-publish-verify",
    "发布前黑盒验证：隔离 venv + 路径，agent 以新用户身份自验任意 skill，产出可用性报告。",
    "验",
  ),
  skill(
    "skill-task-polling",
    "Task Polling",
    "task-polling",
    "以 docs/task.md 为唯一事实源，使用 /loop 自动领取、执行和完成单个本地任务。",
    "轮",
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
  skill(
    "skill-voice-to-me",
    "Voice To Me",
    "voice-to-me",
    "将回复生成自然 MP3 语音，并通过 QQ 发送给用户。",
    "语",
  ),
  skill(
    "skill-weather-search",
    "Weather Search",
    "weather-search",
    "按地点与活动半径查周边天气与空气质量，输出 Markdown 报告与出门防护建议。",
    "天",
  ),
  skill(
    "skill-lan-chat",
    "LAN Chat",
    "lan-chat",
    "零依赖临时局域网聊天室，支持浏览器聊天、文件传输、粘贴图片，同 Wi-Fi 手机电脑即用。",
    "传",
  ),
  skill(
    "skill-md-to-png",
    "MD to PNG",
    "md-to-png",
    "把 Markdown 渲染成 VitePress 风格 HTML，再调用 html-cut 截图为高清 PNG，方便手机查看。",
    "渲",
  ),
]);

const newSkills = skills.filter((item) => item.tag === "new");
if (newSkills.length > 4) {
  throw new Error(`Skill matrix supports at most four new skills; found ${newSkills.length}.`);
}

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
