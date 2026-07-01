export type ShowcaseType = "skill" | "mcp";

export type ShowcaseItem = {
  id: string;
  type: ShowcaseType;
  name: string;
  shortIntro: string;
  /** Skill 的 SKILL.md（raw）地址 */
  documentUrl: string;
  /** MCP 对应 GitHub 仓库，如 gitByEOS/agents-chat-mcp */
  githubRepo?: string;
  displayCommand: string;
  installCommand: string;
  icon: string;
  tag?: "new" | "hot";
};
