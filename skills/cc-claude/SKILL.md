---
name: cc-claude
description: 配置和启动使用自定义 Anthropic 兼容渠道的 Claude Code 实例。当用户请求 cc-claude 或需要配置自定义 Claude 渠道时使用
version: 1.0.0
---

# Custom Channel Claude

## 处理流程

当用户请求 cc-claude 时，先检测是否已有配置：

```bash
ls -la ~/.claude/skills/cc-claude/config/auth
```

若文件存在（权限 `600`），进入已有配置流程；否则进入首次配置。

### 已有配置

使用 AskUserQuestion 提供以下选项（仅选择型，要求 ≥2 项）：

1. **查看当前配置** — 运行 `cc-claude config`，展示脱敏配置
2. **重置配置** — 运行 `cc-claude reset`，重新走首次配置流程
3. **增加模型** — 用户选择后，**直接在对话中询问**模型名，然后调用 `cc-claude add-model <模型名>`
4. **修改 API Key** — 用户选择后，**直接在对话中要求粘贴**新 Key，然后调用 `cc-claude change-token <新Key>`

### 首次配置

使用 AskUserQuestion 收集以下信息，**严格遵从选项**：

1. **API 地址** — 厂商兼容的 Anthropic API 端点 
  - 选项: ["https://api.deepseek.com/anthropic", 自定义URL]  
2. **API Key** — 厂商分配的密钥
  - 选项: ["sk-****86f2c", 自定义Key]
3. **模型列表** — 逗号分隔的模型名
  - 选项: ["deepseek-v4-pro, deepseek-v4-flash", 自定义列表]
4. **快捷命令名** — 默认 `cc-claude`
  - 选项: ["cc-claude", 自定义命令]

收集完毕后调用：
```bash
bash scripts/cc-claude.sh configure --url <URL> --token <TOKEN> --models <MODELS> --name <NAME>
```

配置完成后提示用户在**新终端窗口**运行 `cc-claude`。

## 子命令

| 命令 | 说明 |
|---|---|
| `cc-claude` | fzf/select 选模型并启动 Claude |
| `cc-claude config` | 查看当前配置（脱敏显示） |
| `cc-claude reset` | 重新配置 |
| `cc-claude configure --url .. --token .. --models ..` | 非交互式配置 |
| `cc-claude add-model <模型名>` | 在现有模型列表中新增一个模型 |
| `cc-claude change-token <新Key>` | 替换 API Key（自动加密） |

## 安全说明

所有配置均存储于本地 skill 目录下的 `config/auth` 文件（权限 `600`，仅文件主可读写）。AUTH_TOKEN 使用 `openssl enc -aes-256-cbc -pbkdf2` 加密后存储，密码与 `hostname` + `whoami` 绑定，跨机无法直接解密。`cc-claude config` 输出自动脱敏（前5 + **** + 后5）。

## 脚本文件

- `scripts/cc-claude.sh`：主脚本
- `docs/env-vars.md`：Claude Code 环境变量完整参考
