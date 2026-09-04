# 往期小记

## **时间** : 2026-08-25

**小记** :
- 新增 `bad-solution`，当对 Agent 给出的方案不满意时，强制触发反思机制，适用于代码开发

## **时间** : 2026-08-18

**小记** : 
- 花了四五天开发了 `ESNote` 一个 Mac 高性能 Markdown 编辑器，风格模仿 `Sumblime` 走极简，还支持 CLI  导出图片、HTML、PDF 等，为 Skill 做支持；
- 通知还内嵌了term，支持 `⌘+鼠标` 点开直接跳转文件，方便使用 tui 使用；
- 做这个一是为了测试 grok 能力，二是从零开始再整合一下 Skills，三是自己实际需求，VSCode越来越卡了， Sublime 插件也不满意，而且现在看Markdown的时间可能占80%；
- 不得不感叹，在不需要外部资源依赖的情况下，模仿这块儿 AI 真是太强了。
- 自此我的专武也从三件拓展为四件：专属代理`mock-ollama`、专属TUI`clash`、专属机器人`qbot`、专属Md+Term `esnote`
- 以后想要什么东西全都可以自己加，不过现在还是依赖 `claudecli v2.1.187`，等 `dsh` 完善了可以考虑对接一下

**安装包** : [ESNote-v0.2.3](https://github.com/gitByEOS/open-part-skills/raw/refs/heads/main/tools/esnote/ESNote-v0.2.3.dmg) (1.7M, 仅MacOS)