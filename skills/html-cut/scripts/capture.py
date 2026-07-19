#!/usr/bin/env python3
"""将网页渲染为 PNG 截图。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "缺少 Playwright。请先执行: python3 -m pip install playwright && "
        "python3 -m playwright install chromium",
        file=sys.stderr,
    )
    raise SystemExit(2)

DEFAULT_URL = "http://localhost:2020/"
DEFAULT_OUTPUT = Path("screenshot.png")
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 900
DEFAULT_SCALE = 4
DEFAULT_WAIT = 5000
DEFAULT_TIMEOUT = 45000
WAIT_UNTIL_VALUES = ("load", "domcontentloaded", "networkidle", "commit")
COLOR_SCHEME_VALUES = ("dark", "light")


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是正整数") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="网页 URL → PNG 截图")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="网页 URL，默认本地 2020 端口")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="PNG 输出路径，默认 screenshot.png",
    )
    parser.add_argument("--scale", type=positive_int, default=DEFAULT_SCALE, help="设备像素比，默认 4")
    parser.add_argument("--width", type=positive_int, default=DEFAULT_WIDTH, help="视口宽度，默认 1280")
    parser.add_argument("--height", type=positive_int, default=DEFAULT_HEIGHT, help="视口高度，默认 900")
    parser.add_argument("--wait", type=int, default=DEFAULT_WAIT, metavar="MS", help="加载后额外等待毫秒数，默认 5000")
    parser.add_argument("--timeout", type=positive_int, default=DEFAULT_TIMEOUT, metavar="MS", help="导航超时毫秒数，默认 45000")
    parser.add_argument(
        "--wait-until",
        choices=WAIT_UNTIL_VALUES,
        default="load",
        help="导航完成条件，默认 load",
    )
    parser.add_argument(
        "--color-scheme",
        choices=COLOR_SCHEME_VALUES,
        default="dark",
        help="模拟系统深浅色偏好，默认 dark",
    )
    parser.add_argument(
        "--full-page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否截取完整页面，默认开启；--no-full-page 仅截取当前视口",
    )
    parser.add_argument("--visible", action="store_true", help="显示 Chromium 浏览器窗口")
    args = parser.parse_args()
    if args.wait < 0:
        parser.error("--wait 必须大于或等于 0")
    return args


def capture(
    url: str,
    output: Path,
    *,
    width: int,
    height: int,
    scale: int,
    wait_ms: int,
    timeout_ms: int,
    wait_until: str,
    color_scheme: str,
    full_page: bool,
    visible: bool,
) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not visible)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
                color_scheme=color_scheme,
            )
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            page.screenshot(path=str(output), full_page=full_page)
        finally:
            browser.close()

    return output


def main() -> int:
    args = parse_args()
    try:
        output = capture(
            args.url,
            args.output,
            width=args.width,
            height=args.height,
            scale=args.scale,
            wait_ms=args.wait,
            timeout_ms=args.timeout,
            wait_until=args.wait_until,
            color_scheme=args.color_scheme,
            full_page=args.full_page,
            visible=args.visible,
        )
    except PlaywrightError as exc:
        print(f"截图失败: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"写入截图失败: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
