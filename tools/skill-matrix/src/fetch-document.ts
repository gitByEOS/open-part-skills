import type { ShowcaseItem } from "./types";

async function fetchMcpReadme(githubRepo: string) {
  const response = await fetch(`https://api.github.com/repos/${githubRepo}/readme`, {
    headers: { Accept: "application/vnd.github.raw" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
}

async function fetchSkillDocument(documentUrl: string) {
  const response = await fetch(`${documentUrl}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
}

/** 详情弹窗正文：MCP 走仓库 README API，Skill 走 raw SKILL.md */
export async function fetchShowcaseDocument(item: ShowcaseItem) {
  if (item.type === "mcp") {
    if (!item.githubRepo) {
      throw new Error("缺少 githubRepo");
    }
    return fetchMcpReadme(item.githubRepo);
  }
  return fetchSkillDocument(item.documentUrl);
}
