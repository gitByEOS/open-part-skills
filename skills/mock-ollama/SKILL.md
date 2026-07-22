---
name: mock-ollama
description: 启动 mock-ollama，将 OpenAI Chat Completions、Anthropic Messages、OpenAI Responses 三种协议代理到真实 LLM，并为 Claude Code、Codex/GPT-5.6 与 Cursor 提供本地接入和协议桥接。触发词：mock-ollama、启动 ollama mock、Claude 接第三方模型、Codex 接第三方模型、GPT-5.6 代理、Cursor BYOK、监控 LLM 请求
author: EOS
version: 1.1.0
dependencies:
  - node
  - npm
repository: https://github.com/gitByEOS/open-part-skills
---

# Mock Ollama

`mock-ollama` 把真实 LLM 接口统一代理到本机。

它接收 OpenAI Chat Completions、Anthropic Messages、OpenAI Responses 三种协议；`/api/version`、`/api/tags`、`/api/show` 仅提供 Ollama discovery/metadata 兼容，**不支持** Ollama `/api/chat` 与 `/api/generate`。

## 安装

```bash
npm install -g mock-ollama
mock-ollama -h
```

Cursor 临时公网模式另需安装 `cloudflared`。

## 启动主服务

上游是 OpenAI Chat Completions 时：

```bash
mock-ollama \
  --url "https://open.bigmodel.cn/api/paas/v4" \
  --apikey "你的上游密钥" \
  --api-style chat
```

也可使用环境变量：

```bash
export MOCK_OLLAMA_BASE_URL="https://api.example.com/v1"
export MOCK_OLLAMA_API_KEY="你的上游密钥"
mock-ollama --api-style responses --bridge
```

默认监听 `http://localhost:11434`。

## 协议与 bridge

| 客户端协议 | 本地路由 | 典型客户端 |
|---|---|---|
| Chat Completions | `/v1/chat/completions` | Cursor、OpenAI 兼容 SDK |
| Anthropic Messages | `/v1/messages` | Claude Code |
| OpenAI Responses | `/v1/responses` | Codex、GPT-5.6 |

| 参数 | 说明 |
|---|---|
| `--api-style auto\|anthropic\|responses\|chat` | 指定上游 API 格式，默认 `auto` 自动探测 |
| `--bridge` | 开启 Anthropic、Responses、Chat 三协议 3×3 自动互转 |
| `--url` / `MOCK_OLLAMA_BASE_URL` | 上游 API 根地址 |
| `--apikey` / `MOCK_OLLAMA_API_KEY` | 上游 API Key |
| `--host` / `--port` | 主服务监听地址与端口，默认 `localhost:11434` |
| `--quiet` | 关闭详细控制台日志 |

上游和客户端协议不一致时必须开启 `--bridge`。常见组合：

```bash
# Claude Code → GPT-5.6 / Responses 上游
mock-ollama --url "https://api.example.com/v1" --apikey "你的上游密钥" --api-style responses --bridge

# Codex / GPT-5.6 客户端 → Claude / Anthropic 上游
mock-ollama --url "https://api.anthropic.com" --apikey "你的上游密钥" --api-style anthropic --bridge
```

bridge 支持文本、SSE、工具调用、system 消息和 reasoning；关闭时各协议按原路径、原请求体透明转发。

## Claude Code

Claude Code 使用 Anthropic Messages 路由。若上游不是 Anthropic，主服务必须带 `--bridge`。

```bash
olm_claude() {
    local model="${1:-claude-sonnet-4-6}"
    shift || true
    ANTHROPIC_AUTH_TOKEN=ollama \
    ANTHROPIC_BASE_URL=http://localhost:11434 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    ANTHROPIC_MODEL="$model" \
    ANTHROPIC_DEFAULT_SONNET_MODEL="$model" \
    ANTHROPIC_DEFAULT_OPUS_MODEL="$model" \
    ANTHROPIC_DEFAULT_HAIKU_MODEL="$model" \
    claude --permission-mode acceptEdits --model "$model" "$@"
}

# 例：通过 Responses 上游运行 Claude Code
olm_claude claude-sonnet-4-6
```

## Codex 与 GPT-5.6

Codex 使用 OpenAI Responses 路由。创建一个临时配置文件，不修改现有 `~/.codex/config.toml`：

```toml
# /tmp/mock-ollama-codex.toml
model_provider = "mock-ollama"
model = "gpt-5.6-terra"

[model_providers.mock-ollama]
name = "mock-ollama"
base_url = "http://localhost:11434/v1"
env_key = "MOCK_OLLAMA_CODEX_API_KEY"
wire_api = "responses"
requires_openai_auth = false
```

启动时提供任意非空本地 Bearer 值；主服务使用自己的 `MOCK_OLLAMA_API_KEY` 访问真实上游：

```bash
mkdir -p /tmp/mock-ollama-codex-home
cp /tmp/mock-ollama-codex.toml /tmp/mock-ollama-codex-home/config.toml
MOCK_OLLAMA_CODEX_API_KEY=ollama \
  CODEX_HOME=/tmp/mock-ollama-codex-home \
  codex --model gpt-5.6-terra
```

若上游不是 Responses，启动主服务时增加 `--bridge`。可将 `gpt-5.6-terra` 替换为上游实际模型名。

## Cursor BYOK

不要将带管理接口的 `11434` 直接暴露公网。Cursor 使用独立的最小公网入口：

```bash
# 1. 主服务只留在本机
mock-ollama \
  --url "https://api.example.com/v1" \
  --apikey "你的上游密钥" \
  --api-style responses \
  --bridge

# 2. Cursor 专用入口，默认启动临时 Cloudflare Tunnel
mock-ollama --cursor
```

第二个命令会打印 Cursor Settings → Models 所需配置：

- 打开 `Override OpenAI Base URL`
- 填入打印的 `Base URL`
- 填入打印的 `OpenAI API Key`
- 添加打印的任一模型名，可添加多个模型自由切换

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--cursor` | - | 启动 Cursor BYOK 专用入口 |
| `--cursor-port` | `11435` | Cursor 本机回环端口 |
| `--cursor-api-key` | 随机生成 | 公网入口 Bearer key |
| `--cursor-upstream` | `http://localhost:11434` | 已启动的主服务 |
| `--cursor-tunnel` | `quick` | `quick` 启动临时 Tunnel，`off` 只启动本地入口 |

Cursor 入口仅暴露 `/healthz`、`/v1/models`、`/v1/chat/completions`，除健康检查外均要求 Bearer 认证。`trycloudflare.com` 临时地址每次重启会变化；长期使用应配置受控域名与 Cloudflare Access。

## 检查服务

```bash
curl http://localhost:11434/api/version
curl http://localhost:11434/api/tags

curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "你的模型名",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```
