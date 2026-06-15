#!/usr/bin/env python3
"""
从橘鸦Juya微信公众号专辑定位早报文章，转 RSS item 后导出早茶 HTML。
"""

import argparse
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import juya_utils

ALBUM_URL = "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzIyMDk0MDY1OA==&action=getalbum&album_id=4066755324999598083"


def default_wfp_path():
    return Path(__file__).resolve().parents[2] / "webfetch-plus"


def run_wfp(wfp_path, url, output_file, wait_ms):
    command = f"{url} --wait {wait_ms} --stealth --format html --out {output_file}"
    result = subprocess.run(
        ["bash", "bin/wfp.sh"],
        cwd=wfp_path,
        input=command,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.stderr.write(result.stdout)
        sys.exit(result.returncode)

    if not Path(output_file).exists():
        print(f"❌ webfetch-plus 未生成文件: {output_file}", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        sys.exit(1)


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def resolve_article(args, wfp_path, tmp_dir):
    if args.url:
        print("使用 --url 直链，跳过专辑抓取")
        return {
            "title": "",
            "link": args.url,
            "date": args.date or "",
        }, 0

    if not args.refresh_album:
        article = juya_utils.resolve_article_from_rss(args.date)
        if article:
            print("RSS 解析到微信链接，跳过专辑抓取")
            return article, 0

        article = juya_utils.select_cached_article(args.date)
        if article:
            print("使用专辑缓存，跳过专辑抓取")
            return article, 0

    album_file = Path(tmp_dir) / "album.html"
    print("抓取微信公众号专辑...")
    run_wfp(wfp_path, ALBUM_URL, album_file, args.wait)

    articles = juya_utils.parse_album_articles(read_text(album_file))
    juya_utils.save_album_cache(articles)

    article = juya_utils.select_article(articles, args.date)
    return article, 1


def main():
    parser = argparse.ArgumentParser(description="从微信公众号导出橘鸦Juya早茶 HTML")
    parser.add_argument("output_dir", nargs="?", default="./juya-output", help="输出目录 (默认 ./juya-output)")
    parser.add_argument("--date", "-d", help="指定日期 YYYY-MM-DD (默认最新一期)")
    parser.add_argument("--url", "-u", help="微信文章直链，跳过专辑抓取（仅 1 次 webfetch）")
    parser.add_argument("--refresh-album", action="store_true", help="忽略 RSS/缓存，强制重抓专辑")
    parser.add_argument("--wfp-path", default=os.environ.get("WFP_PATH") or str(default_wfp_path()), help="webfetch-plus 路径")
    parser.add_argument("--wait", type=int, default=5000, help="页面加载后等待毫秒数")
    parser.add_argument("--no-open", action="store_true", help="生成后不自动打开浏览器")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    wfp_path = Path(args.wfp_path).expanduser().resolve()
    if not (wfp_path / "bin" / "wfp.sh").exists():
        print(f"❌ 未找到 webfetch-plus: {wfp_path}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        article, album_wfp_calls = resolve_article(args, wfp_path, tmp_dir)
        if not article:
            print(f"❌ 未找到 {args.date or '最新'} 的早报文章", file=sys.stderr)
            sys.exit(1)

        article_file = Path(tmp_dir) / "article.html"
        print(f"抓取微信文章: {article['title'] or article['link']}")
        run_wfp(wfp_path, article["link"], article_file, args.wait)

        print("转换为 RSS item 并导出早茶 HTML...")
        extracted = juya_utils.extract_wechat_article(
            read_text(article_file),
            fallback_title=article["title"],
            fallback_link=article["link"],
        )
        date_str = extracted["date"] or article["date"] or datetime.now().strftime("%Y-%m-%d")
        output_file = output_dir / f"juya-{date_str}.html"

        rss_item = juya_utils.article_to_rss_item(extracted)
        rss_to_html = juya_utils.load_rss_to_html()
        output_file.write_text(
            rss_to_html.render_item_html(
                rss_item,
                source_label="橘鸦Juya 微信公众号",
                source_link=article["link"],
                source_link_text="微信原文",
            ),
            encoding="utf-8",
        )

    wfp_calls = album_wfp_calls + 1
    print(f"✅ 生成完成: {output_file}")
    print(f"webfetch 调用次数: {wfp_calls}")

    if not args.no_open:
        opener = "open" if platform.system() == "Darwin" else "xdg-open"
        subprocess.run([opener, str(output_file)])


if __name__ == "__main__":
    main()
