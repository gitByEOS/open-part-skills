---
name: closure-graph
description: 检查流程、特效、UI 的衔接是否闭环，列出文档缺口并生成可点击的单文件 HTML；适用于审查需求完整性、排查断点与展示分析结果
version: 1.1.1
dependencies:
  - "python3"
repository: https://github.com/gitByEOS/open-part-skills
---

# closure-graph

把衔接分析画成可点击的 Graph / Node / Edge，最终交付单文件 HTML。

分析由代理阅读材料后完成；渲染脚本只校验 JSON 结构与引用关系，不会自动识别文档缺口。只使用材料中有依据的结论，不凭空补全流程。

## 使用边界

- 需要 Python 3，无需安装第三方 Python 包；生成的 HTML 内置图形资源，可在浏览器离线打开
- 脚本读取指定 JSON，创建输出父目录并写入 HTML；目标已存在会被覆盖，运行前确认路径与覆盖授权
- 不修改原始材料、不上传内容、不发起网络请求；HTML 包含材料摘录，分享前先检查敏感信息
- 节点可点击查看依据与缺口，支持图形缩放、拖动和明暗主题切换

## 步骤

1. 读完材料，整理成下面的 JSON
2. 运行：

```bash
python3 <skill>/scripts/render.py <输入.json> -o <输出.html>
```

3. 回复里给出 HTML 的绝对路径，让用户用浏览器打开
4. 实线表示文档已写后继，虚线表示后继缺失或跳过了必要步骤

## JSON

```json
{
  "title": "页面标题",
  "source": "材料来源，一行",
  "verdict": { "title": "总判", "body": "一句说清断在哪" },
  "lanes": [
    {
      "id": "flow",
      "label": "流程",
      "title": "这张图在看什么",
      "nodes": [
        {
          "id": "spin",
          "title": "短标题",
          "sub": "一行副标题",
          "kind": "ok",
          "gapIds": [],
          "source": "文档里这句话怎么写的"
        },
        {
          "id": "next",
          "title": "后续步骤待补",
          "sub": "文档未说明如何继续",
          "kind": "gap",
          "gapIds": ["back"],
          "source": "材料未描述该节点的后继"
        }
      ],
      "edges": [
        { "from": "spin", "to": "next", "kind": "gap", "label": "后继待补" }
      ],
      "closed": [["已经接上的衔接", "依据"]]
    }
  ],
  "gaps": [
    {
      "id": "back",
      "lanes": ["flow"],
      "severity": "断后继",
      "title": "缺口名",
      "fact": "文档里实际有的",
      "need": "要补上的"
    }
  ]
}
```

`kind` 只允许 `ok`、`decision`、`gap`、`conflict`、`param`。边的 `kind` 只允许 `ok`、`gap`。`severity` 只允许 `断后继`、`冲突`、`缺参数`。

`gapIds` 必须能在 `gaps` 里找到。边的两端必须是节点。`lanes` 用 `flow`、`fx`、`ui` 这三张图，缺哪张就不要编一张空的。