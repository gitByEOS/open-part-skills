---
name: mock-ollama
description: 启动 mock-ollama 服务，模拟 Ollama API 代理到真实 LLM，监控请求响应数据并提供 Dashboard。触发词：mock-ollama、启动 ollama mock、监控 LLM 请求、查看 LLM 调用统计
version: 1.0.0
repository: https://github.com/gitByEOS/open-part-skills
---

# Mock Ollama

模拟 Ollama API 代理到真实 LLM，监控请求/响应、Token用量、Tool Calls分布，提供 Dashboard 可视化。

## 安装

```bash
npm install -g mock-ollama
```

## 启动示例

```bash
# DeepSeek（需设置环境变量）
export MOCK_OLLAMA_BASE_URL="https://api.deepseek.com"
export MOCK_OLLAMA_API_KEY="sk-xxx"
mock-ollama --open

# 智谱 GLM（命令行参数）
mock-ollama --url "https://open.bigmodel.cn/api/paas/v4" --apikey "xxx" --open
```

## 参数

| 参数 | 环境变量 | 说明 |
|------|----------|------|
| `--url` | `MOCK_OLLAMA_BASE_URL` | 上游 LLM API 地址 |
| `--apikey` | `MOCK_OLLAMA_API_KEY` | 上游 API Key |
| `--port` | - | 监听端口，默认 11434 |
| `--open` | - | 启动后自动打开 Dashboard |
| `--max_context` | - | Dashboard 上下文上限，默认 200000 |

## 用法

启动 mock-ollama 后，使用以下函数启动 Claude Code：

```bash
olm_claude() {
    local model="${1:-glm-5}"
    ANTHROPIC_AUTH_TOKEN=ollama \
    ANTHROPIC_BASE_URL=http://localhost:11434 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    ANTHROPIC_MODEL="$model" \
    ANTHROPIC_DEFAULT_SONNET_MODEL="$model" \
    ANTHROPIC_DEFAULT_OPUS_MODEL="$model" \
    ANTHROPIC_DEFAULT_HAIKU_MODEL="$model" \
    claude --permission-mode acceptEdits --model "$model" "$@"
}

# 使用：olm_claude glm-5
```