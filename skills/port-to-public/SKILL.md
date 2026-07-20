---
name: port-to-public
description: >-
  临时将本机 loopback HTTP(S) 服务经 Cloudflare Quick Tunnel 暴露到公网。支持启动、状态、路径验证和停止；仅用于短时联调，默认 12 小时自动失效。用户提到“暴露端口到公网”“临时公网 URL”“Quick Tunnel”“让外网访问 localhost”时使用。
version: 1.0.0
dependencies:
  - "python>=3.10"
  - esflow
repository: https://github.com/gitByEOS/open-part-skills
---

# Port to Public

将本机 `localhost`、`127.0.0.1` 或 `::1` 上的 HTTP(S) 服务临时暴露为随机
`https://*.trycloudflare.com` 地址。

> **安全边界**：公网 URL 无认证，拿到 URL 的人都能访问目标服务。禁止暴露管理面板、数据库控制台、密钥服务或无认证写接口。仅适合短时联调，不支持 TCP、固定域名、认证、长期运行或高可用。公网 URL 不可视为机密——`trycloudflare` 域名可被枚举，`stop` 后 URL 立即失效但 CDN 缓存可能残留。

## 使用

```bash
SKILL_ROOT="<此 skill 的绝对路径>"

# 启动：必须明确确认公网暴露；默认 12 小时后失效
python3 "$SKILL_ROOT/scripts/run.py" start  --port 11434 --confirm-public --ttl 1800

# 查看同一端口的 tunnel 状态
python3 "$SKILL_ROOT/scripts/run.py" status --port 11434

# 验证公网根路径，或验证指定路径与内容标记
python3 "$SKILL_ROOT/scripts/run.py" verify --port 11434
python3 "$SKILL_ROOT/scripts/run.py" verify --port 11434 --path /api/tags --expect models

# 联调结束立即停止；重复执行安全且幂等
python3 "$SKILL_ROOT/scripts/run.py" stop --port 11434
```

也可使用 loopback URL：

```bash
python3 "$SKILL_ROOT/scripts/run.py" start --url https://localhost:8443 --no-tls-verify --confirm-public
```



## 参数


| 参数                     | 适用动作     | 说明                                                    |
| ---------------------- | -------- | ----------------------------------------------------- |
| `--port <1-65535>`     | 全部       | 本机 HTTP 服务端口                                          |
| `--url <URL>`          | 全部       | loopback HTTP(S) URL；与 `--port` 互斥，同时给则报错退出 1         |
| `--confirm-public`     | `start`  | 必填确认；明确该 URL 无认证                                      |
| `--ttl <秒>`            | `start`  | 自动停止时间，默认 `43200`（12 小时），范围 1–86400，超出报错退出 1（不 clamp） |
| `--path <相对路径>`        | `verify` | 本次公网验证路径，默认 `/`                                       |
| `--expect <文本>`        | `verify` | 响应正文必须包含的标记；正文不会输出                                    |
| `--timeout <秒>`        | `start`  | 等待 tunnel 注册时间，默认 120                                 |
| `--verify-timeout <秒>` | `verify` | 公网请求超时，默认 20                                          |
| `--protocol http2      | quic`    | `start`                                               |
| `--no-tls-verify`      | `start`  | 允许本机自签名 HTTPS                                         |
| `--schema`             | 任意       | 输出 JSON 契约                                            |


> `--port` 应指向本机已监听的 loopback 服务端口。若端口被占，先确认目标服务是否真的在跑，或换端口重启目标服务后再暴露。



## 输出与生命周期

- stdout 输出一行 JSON，遵循标准信封 `{ok, data, error, meta}`：
  - 成功：`ok=true`，`data` 含 `action/status/local_url/public_url/running/pid/expires_at/verification/stop/stop_command`
  - 失败：`ok=false`，`data=null`，`error` 含 `{code, message, retryable}`
- `data.status` 取值：`started`（新建）/`running`（复用或状态查询）/`verified`/`stopped`/`already_stopped`
- esflow 节点事件与错误诊断写入 stderr，不会污染机器读取 stdout
- 所有状态仅存于 `~/.cache/port-to-public/<session_hash>/`，没有用户产物，也不需要 `--out`
- 同一个规范化 loopback URL 映射至同一内部会话，因此 `status`、`verify`、`stop` 只需重复相同的 `--port` 或 `--url`
- 到达 TTL 后，下一次本 skill 操作会清理过期 tunnel；联调结束请主动 `stop`
- 会话目录在 `stop` 后保留 `cloudflared.log` 供事后排查，可手工删除整个 session_dir



## 节点(6 个)

| id | depth | 职责 |
|---|---|---|
| `validate_request` | 0 | 解析 CLI 入参、规范化 loopback 目标、`start` 时探测本地服务 |
| `inspect_tunnel` | 1 | 读取并核验 session_dir 的 tunnel 状态，过期自动清理 |
| `launch_tunnel` | 2 | 仅 `start`：启动或复用 Cloudflare Quick Tunnel，写 state |
| `stop_tunnel` | 2 | 仅 `stop`：停止本 skill 创建且身份匹配的进程组 |
| `verify_public` | 3 | 仅 `start`/`verify`：公网 URL 路径验证，支持 `--expect` 标记 |
| `render_result` | 4 | 聚合上游产物为 stdout envelope 的 `data` 部分 |

## esflow DAG

```text
validate_request → inspect_tunnel → launch_tunnel → verify_public → render_result
                             ├────→ stop_tunnel ────────────────────┘
                             ├────→ launch_tunnel ─→ render_result
                             ├────→ verify_public ──→ render_result
                             └────────────────────→ render_result
```

节点按 `action` 自动分流：`launch_tunnel` 仅 `start` 执行，`verify_public` 仅 `start`/`verify` 执行，`stop_tunnel` 仅 `stop` 执行，`render_result` 恒为终点。

- `start`：校验本地服务 → 检查/复用会话 → 启动 tunnel → 验证公网根路径
- `status`：校验请求 → 检查会话 → 输出状态
- `verify`：校验请求 → 检查会话 → 验证 `--path`
- `stop`：校验请求 → 检查会话 → 仅停止本 skill 创建且身份匹配的进程组



## 退出码

- `0`：动作成功（含 `already_stopped` 这种"动作完成但无需变更"的场景）
- `1`：参数、依赖、本地服务、tunnel 或公网验证失败



## 依赖

**pip 依赖**（frontmatter `dependencies` 字段）：

- `esflow`

**系统依赖**（需手动安装，非 pip 包）：

```bash
brew install cloudflared      # macOS
# apt install cloudflared     # Linux，参考 Cloudflare 官方源
```

> 仅支持 macOS / Linux。`stop` 依赖 `ps -o lstart=` 做进程身份校验，Windows 下不可用。

