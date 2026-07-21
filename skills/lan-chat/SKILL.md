---
name: lan-chat
description: 创建、定制并运行零依赖的临时局域网聊天室，支持浏览器聊天、文件传输、粘贴图片与桌面/移动端响应式布局。用户需要局域网聊天页、临时 Wi-Fi 文件共享，或修改内置聊天 UI 时使用。
version: 1.0.0
dependencies:
  - python3
repository: https://github.com/gitByEOS/open-part-skills
---

# 局域网聊天

在同 Wi-Fi 下快速搭一个临时聊天页：发消息、传文件、粘贴图片，手机电脑都能用。

## 启动

```bash
python3 scripts/lan_chat.py --work-dir /path/to/workspace
```

终端输出局域网地址（默认端口 `11567`），同网设备浏览器打开即可。上传文件写入工作区的 `lan_chat_uploads/`，停服即清空。

## 参数

| 参数 | 说明 |
|---|---|
| `--work-dir` | 工作区路径，默认当前目录 |
| `--port` | 监听端口，默认 `11567` |

```bash
python3 scripts/lan_chat.py --work-dir . --port 8080
```

## 功能

- **聊天**：Enter 发送，Shift+Enter 换行
- **文件**：单文件最大 2 GiB
- **粘贴图片**：输入框直接粘贴作为附件
- **成员列表**：侧栏显示在线昵称与 IP，窄屏可折叠
- **气泡**：本机消息在右，他人消息在左（按浏览器 `member_id` 区分）

## 约束

- 用 `--work-dir` 指向用户工作区，不要复制脚本
- 启动后**必须**把终端打印的局域网 URL 原样告知用户，让用户手机点击可直接打开
- 脚本通过 `flush=True` 即时输出 URL，agent 须从终端读取该行作为唯一 URL 来源
- 代发消息：

```bash
curl --fail -X POST http://127.0.0.1:11567/api/messages \
  -H 'Content-Type: application/json' \
  --data-binary '{"name":"昵称","text":"消息内容","member_id":"唯一标识"}'
```

- 代发文件（`file=@` 用绝对路径）：

```bash
curl --fail -X POST http://127.0.0.1:11567/api/files \
  -F 'name=昵称' \
  -F 'member_id=唯一标识' \
  -F 'file=@/absolute/path/to/file;filename=显示名.ext'
```

- 自定义端口时，上述 URL 端口号一并替换
- 请求体用 `member_id` 标识发送者，响应 JSON 中同字段名为 `sender_id`
