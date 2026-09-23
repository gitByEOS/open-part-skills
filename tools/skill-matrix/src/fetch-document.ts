import type { ShowcaseItem } from "./types";

export type SkillFile = { path: string; size: number; isPreviewable: boolean };

const skillRepo = "https://raw.githubusercontent.com/gitByEOS/open-part-skills/main";
const skillTreeUrl = "https://api.github.com/repos/gitByEOS/open-part-skills/git/trees/main?recursive=1";
const previewableExtensions = new Set(["md", "py", "js", "mjs", "ts", "tsx", "json", "html", "css", "sh", "lua", "txt", "yml", "yaml", "toml"]);
const maxPreviewSize = 1024 * 1024;

type GitHubTree = { truncated: boolean; tree: Array<{ path: string; type: string; size?: number }> };
let skillTreeRequest: Promise<GitHubTree> | null = null;

function skillFolder(item: ShowcaseItem) {
  const url = new URL(item.documentUrl);
  const match = url.pathname.match(/^\/gitByEOS\/open-part-skills\/main\/skills\/([a-z0-9-]+)\/SKILL\.md$/);
  if (url.origin !== "https://raw.githubusercontent.com" || !match) {
    throw new Error("无效的 Skill 文档路径");
  }
  return match[1];
}

function isSafeSkillPath(path: string) {
  return path.split("/").every((segment) => segment !== "" && segment !== "." && segment !== "..");
}

function isPreviewableFile(path: string, size: number) {
  const name = path.split("/").at(-1) ?? "";
  const extension = name.split(".").pop()?.toLowerCase() ?? "";
  return isSafeSkillPath(path) && (previewableExtensions.has(extension) || !name.includes(".")) && size <= maxPreviewSize;
}

function fetchSkillTree() {
  if (!skillTreeRequest) {
    skillTreeRequest = fetch(skillTreeUrl)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = (await response.json()) as GitHubTree;
        if (result.truncated || !Array.isArray(result.tree)) throw new Error("文件列表不完整");
        return result;
      })
      .catch((error: unknown) => {
        skillTreeRequest = null;
        throw error;
      });
  }
  return skillTreeRequest;
}

/** 文件清单限定为当前 Skill 目录，预览只接受小于 1MB 的文本文件 */
export async function fetchSkillFiles(item: ShowcaseItem): Promise<SkillFile[]> {
  const root = `skills/${skillFolder(item)}/`;
  const { tree } = await fetchSkillTree();
  return tree
    .filter((entry) => entry.type === "blob" && entry.path.startsWith(root))
    .map((entry) => {
      const path = entry.path.slice(root.length);
      const size = entry.size ?? 0;
      return { path, size, isPreviewable: isPreviewableFile(path, size) };
    })
    .filter((file) => isSafeSkillPath(file.path))
    .sort((left, right) => left.path.localeCompare(right.path, "en"));
}

/** 只读取清单中可预览的仓库文件，避免任意路径与二进制文本读取 */
export async function fetchSkillFile(item: ShowcaseItem, file: SkillFile) {
  if (!file.isPreviewable || !isPreviewableFile(file.path, file.size)) {
    throw new Error("该文件不可预览");
  }
  const path = file.path.split("/").map(encodeURIComponent).join("/");
  const response = await fetch(`${skillRepo}/skills/${skillFolder(item)}/${path}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const content = await response.text();
  if (new TextEncoder().encode(content).length > maxPreviewSize) throw new Error("文件超过预览大小限制");
  return content;
}

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
