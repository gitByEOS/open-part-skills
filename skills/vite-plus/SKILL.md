---
name: vite-plus
description: 最新适合 Agent 开发的 Web 前端工具链。当需要开发 Vite+ 项目、执行 vp 命令或配置 Vite+ 工具链时使用此技能
version: 1.0.0
repository: https://github.com/gitByEOS/open-part-skills
---

# Vite+ (vp) 使用技能

## 概述

Vite+ 是整合了运行时管理、包管理、开发/构建/测试、格式化和 lint 的一体化前端工具链，CLI 命令为 `vp`。

## 何时使用

当用户提到以下意图时触发：
- 创建 Vite+ 项目
- 运行 vp 命令（vp dev、vp build、vp check 等）
- 配置 Vite+ 或迁移到 Vite+

## 安装 vp

```bash
curl -fsSL https://vite.plus | bash
```

验证：`vp help`
升级：`vp upgrade`

## 创建项目

交互式创建：
```bash
vp create
```

非交互式指定模板：
```bash
vp create vite -- --template vanilla-ts # 传递参数给模板
```

常用模板：
| 值 | 含义 |
|----|------|
| `vanilla` | 原生 JavaScript |
| `vanilla-ts` | 原生 TypeScript |
| `vue` | Vue + JavaScript |
| `vue-ts` | Vue + TypeScript |
| `react` | React + JavaScript |
| `react-ts` | React + TypeScript |
| `react-swc` | React + JavaScript（SWC） |
| `react-swc-ts` | React + TypeScript（SWC） |
| `svelte` | Svelte + JavaScript |
| `svelte-ts` | Svelte + TypeScript |
| `preact` | Preact + JavaScript |
| `preact-ts` | Preact + TypeScript |
| `lit` | Lit + JavaScript |
| `lit-ts` | Lit + TypeScript |
| `solid` | Solid + JavaScript |
| `solid-ts` | Solid + TypeScript |
| `qwik` | Qwik + JavaScript |
| `qwik-ts` | Qwik + TypeScript |


## 核心命令

```bash
vp dev              # 启动开发服务器
vp build            # 生产构建
vp build --watch    # 构建并监听
vp preview          # 本地预览生产构建
vp check            # 格式化 + lint + 类型检查（一次完成）
vp check --fix      # 检查并自动修复
vp fmt              # 仅格式化
vp fmt --check      # 检查格式而不修改
vp lint             # 仅 lint
vp lint --fix       # lint 并自动修复
vp test             # 运行测试
vp test watch       # 监听模式测试
vp run <script>     # 运行 package.json 脚本
```

## 包管理

```bash
vp install          # 安装依赖
vp add <pkg>        # 添加依赖
vp add -D <pkg>     # 添加开发依赖
vp remove <pkg>     # 移除
vp update           # 更新
vp cache clean      #清缓存
```

## 配置文件

### Vite 构建配置（vite.config.ts）
最小可用配置：
```typescript
import { defineConfig } from "vite";

export default defineConfig({
  base: "/skill_matrix/",
  plugins: [],
  build: {
    outDir: "/Users/bole/Server/skill_matrix",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5175,
    strictPort: true,
  },
});

```

### 项目说明（package.json）
最小可用配置：
```json
{
  "name": "skill_matrix",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vp dev",
    "build": "tsc && vp build",
    "preview": "vp preview",
    "check": "vp check"
  },
  "dependencies": {
    "typescript": "latest",
    "vite": "latest"
  },
  "packageManager": "pnpm@11.0.9"
}
```

## CI/CD（GitHub Actions）

```yaml
- uses: voidzero-dev/setup-vp@v1
  with:
    node-version: '22'
    cache: true
- run: vp install
- run: vp check
- run: vp test
- run: vp build
```

## 核心原则

- 用 `vp check` 代替单独运行格式化/lint/类型检查
- 用 `vp run` 执行 package.json 脚本，用 `vp test` 执行内置测试
- 不再直接使用 prettier/eslint/vitest，统一在 `vite.config.ts` 中配置
