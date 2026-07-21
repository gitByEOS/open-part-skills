---
name: html-cut
description: 用 Playwright 将网页或本地 HTML 渲染为高清 PNG 截图，支持全页、视口、分辨率和加载等待控制。用户提到 html-cut、cut-html、网页截图、HTML 截图、网页转 PNG、全页长截图时使用。
version: 1.0.0
dependencies:
  - python3
  - playwright
repository: https://github.com/gitByEOS/open-part-skills
---

# HTML Cut

将网页 URL 或本地 HTML 页面渲染为高清 PNG 截图，默认输出全页截图。

## 常见示例

命令应在本 skill 根目录执行，成功时 stdout 仅输出截图绝对路径。

### 远程网页与深浅色

```bash
# 默认按亮色偏好渲染，全页高清截图
python3 scripts/capture.py https://example.com /tmp/example.png

# 指定暗色偏好
python3 scripts/capture.py https://example.com /tmp/example-dark.png --color-scheme dark
```

### 本地开发服务

页面存在入场动画或接口请求时，留出额外渲染时间：

```bash
python3 scripts/capture.py http://localhost:5173 /tmp/home.png \
  --width 1440 --height 900 --scale 2 --wait 2000
```

### 本地 HTML 文件

`file:///` 后必须是绝对路径：

```bash
python3 scripts/capture.py "file:///Users/name/project/dist/index.html" \
  /tmp/page.png --wait 500
```

### 仅截取首屏

```bash
python3 scripts/capture.py https://example.com /tmp/viewport.png \
  --width 390 --height 844 --scale 3 --no-full-page
```

### 等待 SPA 网络稳定

```bash
python3 scripts/capture.py http://localhost:3000 /tmp/app.png \
  --wait-until networkidle --wait 1000
```

## 参数

| 参数 | 说明 |
|---|---|
| `url` | 网页 URL；可省略，默认 `http://localhost:2020/` |
| `output` | PNG 输出路径；可省略，默认当前目录 `screenshot.png` |
| `--scale N` | 设备像素比，默认 `4`；值越大图片越清晰、文件越大 |
| `--width N` | 视口宽度，默认 `1280` |
| `--height N` | 视口高度，默认 `900` |
| `--wait MS` | 导航完成后的额外等待时间，默认 `5000`；动态页面可调大 |
| `--timeout MS` | 导航超时，默认 `45000` |
| `--wait-until load\|domcontentloaded\|networkidle\|commit` | 导航完成条件，默认 `load` |
| `--color-scheme dark\|light` | 模拟系统深浅色偏好，默认 `light` |
| `--full-page` / `--no-full-page` | 是否截取完整页面；默认全页，后者仅截取当前视口 |
| `--visible` | 显示 Chromium 窗口，方便排查渲染问题 |

## 工作流

1. 确认目标 URL 可访问；本地文件使用绝对 `file:///` URL
2. 根据目标画面选定输出路径和视口尺寸
3. 动态内容未稳定时，加 `--wait` 或改用 `--wait-until networkidle`
4. 执行截图后，检查 stdout 中的 PNG 路径和图像尺寸

## 输出约定

- 输出格式为 PNG
- 未存在的输出父目录会自动创建
- 默认全页截图，保留页面完整纵向内容
- 默认 `1280×900` 逻辑视口、`4x` 设备像素比，图片实际像素会随页面和 scale 增大
- 不修改网页源码，也不上传页面内容

## 故障排查

| 现象 | 处理 |
|---|---|
| `缺少 Playwright` | 执行 `python3 -m pip install playwright` |
| Chromium 找不到 | 执行 `python3 -m playwright install chromium` |
| 页面超时 | 检查 URL；适当提高 `--timeout`，或改 `--wait-until domcontentloaded` |
| 截图缺少异步内容 | 增大 `--wait`；必要时使用 `--visible` 检查页面 |
| 图片过大 | 降低 `--scale`，或加 `--no-full-page` |

## Agent 注意

- 用户没有给出路径时，输出到临时目录，避免覆盖项目已有文件
- 优先截图本地开发服务；本地 HTML 必须转为绝对 `file:///` URL
- 截图完成后反馈绝对 PNG 路径；不要把二进制图片内容粘进回复
