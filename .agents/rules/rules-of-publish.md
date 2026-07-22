# Open-Part-Skills 更新与发布规则

本规则适用于向本仓库新增、修改、下架或发布任意 Skill、脚本、工具与文档。

## 发布原则

- Skill 的行为、文档、README 登记和测试必须同步，禁止只更新其中一项
- 新增或变更外部副作用（网络、文件删除、发布、鉴权、收费 API）时，必须在 `SKILL.md` 明确边界
- 发布前必须做脱敏，不得泄露私钥、令牌、本地配置、本地路径、用户信息
- Skill 目录下不要提交 `__pycache__/`、`.pyc`、`tests/`、临时 JSON、日志或本地工作区文件

## 变更类型与必改文件

### 规范化新 Skill

必须修改：

1. 规范化 `skills/<skill-name>/SKILL.md` 表头
2. 在 `README.md` 中增加索引和简介
3. 确认 `SKILL.md` 描述和真实脚本实际逻辑无分歧
4. 确认 `SKILL.md` 语境是面向用户而不是开发者，描述规范可以参考项目下其他 skill

`SKILL.md` 必须包含规范 YAML 表头：

```yaml
---
name: <skill-name>
description: <功能、触发语句与适用场景>
author: EOS
version: 1.0.0
dependencies:
  - <运行时依赖>
repository: https://github.com/gitByEOS/open-part-skills
---
```

README 登记位置：

- 通用能力：`README.md` 的 `## Skills` 表
- QQ 机器人能力：`README.md` 的 `## QBot-Skills` 表
- 工具：`README.md` 的 `## Tools` 表
- MCP 服务：`README.md` 的 `## MCPs` 表

新条目必须使用相对链接，说明聚焦用户价值，并与表头列数一致。

### 修改既有 Skill

至少检查并按需修改：

1. `skills/<skill-name>/SKILL.md`：能力、触发条件、参数、依赖、限制和示例
2. `skills/<skill-name>/scripts/`：实际实现
3. `skills/<skill-name>/tests/`：新增行为、回归风险与异常路径
4. `skills/<skill-name>/verify.cases/`：真实用户需求的黑盒验证用例
5. `README.md`：名称、说明、版本或分类发生变化时同步更新

若修改用户可见行为、输入输出格式、持久化格式、依赖或安全边界，必须递增 `SKILL.md` 的 `version`：

- 修复兼容缺陷：补丁版本，如 `1.0.0 → 1.0.1`
- 新增兼容能力：次版本，如 `1.0.0 → 1.1.0`
- 破坏兼容性：主版本，如 `1.0.0 → 2.0.0`

## 发布前验证


### 黑盒发布验证

所有待发布 Skill 必须使用 [`skill-publish-verify`](../../skills/skill-publish-verify/SKILL.md) 完成新用户视角验证。

每个待验场景在 `skills/<skill-name>/verify.cases/` 创建一个 JSON：

```json
{
  "skill_path": "<待验 Skill 根目录>",
  "demand": "<真实用户需求>"
}
```

验证流程：

1. 执行 `python3 skills/skill-publish-verify/scripts/run.py <case.json>`
2. 根据 `_agent_run_brief.json`，在隔离环境中阅读 `SKILL.md` 并实际使用待验 Skill
3. 将产物路径写入 `run_record.json`，执行首次 `--resume`
4. 阅读 `_agent_report_brief.json`、`verify_facts.json` 与 `run_record.json`，写入 `skill_verify_report.md`
5. 执行第二次 `--resume` 收尾，并审阅最终报告与产物

`skill_verify_report.md` 必须包含：可用性评分、卡壳点、文档问题、产物结论、改进建议。

报告中发现的卡壳点、文档问题或产物缺陷必须修复；修复后重新运行对应验证用例。

### 技能矩阵更新

新增、下架或修改 Skill 的名称、描述、版本、封面、分类或展示内容时，必须同步检查并按需修改：

1. `tools/skill-matrix/src/showcase-items.ts`：技能卡片数据与展示顺序
2. `tools/skill-matrix/src/types.ts`：展示数据结构变化时更新类型
3. `tools/skill-matrix/src/main.tsx` 及相关组件：展示逻辑变化时更新
4. `tools/skill-matrix/dist/`：构建后的静态站点产物

完成修改后在 `tools/skill-matrix/` 执行：

```bash
npm run build
```

### 验收后暂存

完成实现和全部验证后，执行：

```bash
git diff --check
git status --short
git add <已验收文件>
git diff --cached --check
git diff --cached
```

验收项：

- 不存在空白错误
- 未误带入缓存、临时文件
- 修改范围与需求一致
- README 中链接存在、表格列数正确
- YAML 表头完整，且 `name` 与目录名一致
- 暂存区只包含已验收文件

暂存仅表示待用户验收；不得自行执行 `git commit`、`git push` 或任何外部发布操作。等待用户明确验收并要求提交后，才可以创建提交。

## 发布检查清单

- [ ] 需求对应的实现已完成
- [ ] `SKILL.md` 文档与实际行为一致
- [ ] YAML 表头、版本号和依赖已更新
- [ ] README 中的分类、链接、说明和版本已同步
- [ ] 技能展示信息变化时，`tools/skill-matrix/` 与 `dist/` 已同步并构建通过
- [ ] 测试和黑盒验证用例已新增或更新
- [ ] 编译、静态检查和单元测试均通过
- [ ] `skill-publish-verify` 已通过，报告与产物已审阅
- [ ] 已执行 `git diff --check` 与 `git status --short`
- [ ] 已暂存全部且仅有已验收文件
- [ ] 已审阅 `git diff --cached`
- [ ] 正在等待用户验收与提交指令
- [ ] 未经用户明确要求，不提交、推送或发布到外部平台
