#!/usr/bin/env python3
"""
橘鸦早报脚本共用工具。
"""

import html as html_mod
from html.parser import HTMLParser
import importlib.util
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

ALBUM_CACHE_TTL = 6 * 3600
WECHAT_LINK_RE = re.compile(r"https?://mp\.weixin\.qq\.com/\S+")


def load_rss_to_html():
    script_path = Path(__file__).with_name("rss-to-html.py")
    spec = importlib.util.spec_from_file_location("juya_rss_to_html", script_path)
    if not spec or not spec.loader:
        raise RuntimeError("无法加载 rss-to-html.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_text(html):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", html)).strip()


def normalize_wechat_content(content_html):
    content_html = re.sub(r'\sdata-src="([^"]+)"', r' src="\1"', content_html)
    content_html = re.sub(r'\sdata-original-style="[^"]*"', "", content_html)
    content_html = sanitize_wechat_html(content_html)
    return normalize_content_links(content_html)


def normalize_content_links(content_html):
    content_html = expand_url_code_blocks(content_html)
    content_html = flatten_url_code_list_items(content_html)
    return content_html


def _extract_url_lines(inner_html):
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = html_mod.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return []
    if not all(re.match(r"^https?://\S+$", line) for line in lines):
        return []
    return lines


def expand_url_code_blocks(content_html):
    def replace_code(match):
        inner = match.group(1)
        urls = _extract_url_lines(inner)
        if not urls:
            return match.group(0)
        if len(urls) == 1:
            url = html_mod.escape(urls[0])
            return f'<p class="ref-link"><a href="{url}" target="_blank">{url}</a></p>'
        items = "".join(
            f'<li><a href="{html_mod.escape(url)}" target="_blank">{html_mod.escape(url)}</a></li>'
            for url in urls
        )
        return f'<ul class="ref-links">{items}</ul>'

    return re.sub(
        r"<code>((?:(?!</code>).)*)</code>",
        replace_code,
        content_html,
        flags=re.DOTALL | re.IGNORECASE,
    )


def flatten_url_code_list_items(content_html):
    def replace_ul(match):
        ul_inner = match.group(1)
        if 'class="ref-links"' in match.group(0):
            return match.group(0)

        li_blocks = re.findall(r"<li>(.*?)</li>", ul_inner, re.DOTALL | re.IGNORECASE)
        if not li_blocks:
            return match.group(0)

        urls = []
        for block in li_blocks:
            block = block.strip()
            code_match = re.fullmatch(r"<code>(https?://[^<]+)</code>", block, re.IGNORECASE)
            if not code_match:
                return match.group(0)
            urls.append(code_match.group(1))

        items = "".join(
            f'<li><a href="{html_mod.escape(url)}" target="_blank">{html_mod.escape(url)}</a></li>'
            for url in urls
        )
        return f'<ul class="ref-links">{items}</ul>'

    return re.sub(r"<ul>(.*?)</ul>", replace_ul, content_html, flags=re.DOTALL | re.IGNORECASE)


class WechatHTMLCleaner(HTMLParser):
    allowed_tags = {
        "a",
        "blockquote",
        "br",
        "code",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "img",
        "li",
        "ol",
        "p",
        "strong",
        "ul",
    }
    void_tags = {"br", "img"}
    skip_tags = {"script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in self.allowed_tags:
            return

        attrs_dict = dict(attrs)
        kept_attrs = []
        if tag == "a" and attrs_dict.get("href"):
            kept_attrs.append(("href", attrs_dict["href"]))
            kept_attrs.append(("target", "_blank"))
        elif tag == "img":
            src = attrs_dict.get("src") or attrs_dict.get("data-src")
            if not src:
                return
            kept_attrs.append(("src", src))
            if attrs_dict.get("alt"):
                kept_attrs.append(("alt", attrs_dict["alt"]))

        attrs_html = "".join(
            f' {name}="{html_mod.escape(value, quote=True)}"'
            for name, value in kept_attrs
        )
        self.parts.append(f"<{tag}{attrs_html}>")

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth or tag not in self.allowed_tags or tag in self.void_tags:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(html_mod.escape(data))

    def handle_entityref(self, name):
        if not self.skip_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip_depth:
            self.parts.append(f"&#{name};")


def sanitize_wechat_html(content_html):
    cleaner = WechatHTMLCleaner()
    cleaner.feed(content_html)
    cleaner.close()
    return "".join(cleaner.parts)


def extract_wechat_article(article_html, fallback_title="", fallback_link=""):
    title = fallback_title
    title_match = re.search(r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>', article_html, re.DOTALL)
    if title_match:
        title = clean_text(title_match.group(1)) or fallback_title

    content_match = re.search(
        r'<div[^>]*id="js_content"[^>]*>(.*?)<div[^>]*id="js_content_end"',
        article_html,
        re.DOTALL,
    )
    if not content_match:
        raise ValueError("未找到微信正文 js_content")

    date_match = re.search(r"\d{4}-\d{2}-\d{2}", title)
    date_str = date_match.group() if date_match else datetime.now().strftime("%Y-%m-%d")

    return {
        "title": title,
        "link": fallback_link,
        "date": date_str,
        "content": normalize_wechat_content(content_match.group(1).strip()),
    }


def article_to_rss_item(article):
    title = html_mod.escape(article["title"])
    link = html_mod.escape(article["link"])
    content = article["content"].replace("]]>", "]]]]><![CDATA[>")
    return f"""
<item>
  <title>{title}</title>
  <link>{link}</link>
  <content:encoded><![CDATA[{content}]]></content:encoded>
</item>
    """


def album_cache_path():
    cache_dir = Path.home() / ".cache" / "juya"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "wx-album-index.json"


def load_album_cache():
    path = album_cache_path()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if (datetime.now() - fetched_at).total_seconds() > ALBUM_CACHE_TTL:
            return None
        return data["articles"]
    except (OSError, ValueError, KeyError):
        return None


def save_album_cache(articles):
    album_cache_path().write_text(
        json.dumps(
            {
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "articles": articles,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_album_articles(album_html):
    articles = []
    for tag in re.findall(r'<li\b[^>]*class="[^"]*js_album_item[^"]*"[^>]*>', album_html):
        attrs = {}
        for key, value in re.findall(r'([:\w-]+)="([^"]*)"', tag):
            attrs[key] = html_mod.unescape(value)

        title = attrs.get("data-title", "").strip()
        link = attrs.get("data-link", "").strip()
        if not title or not link:
            continue

        date_match = re.search(r"\d{4}-\d{2}-\d{2}", title)
        articles.append({
            "title": title,
            "link": link,
            "date": date_match.group() if date_match else "",
        })

    return articles


def select_article(articles, target_date=None):
    if target_date:
        for article in articles:
            if article.get("date") == target_date:
                return article
        return None

    return articles[0] if articles else None


def select_cached_article(target_date=None):
    articles = load_album_cache()
    if not articles:
        return None
    return select_article(articles, target_date)


def _article_from_rss_item(item_xml):
    title_match = re.search(r"<title>([^<]+)</title>", item_xml)
    link_match = re.search(r"<link>([^<]+)</link>", item_xml)
    if not link_match:
        return None

    title = html_mod.unescape(title_match.group(1).strip()) if title_match else ""
    link = html_mod.unescape(link_match.group(1).strip())
    if "mp.weixin.qq.com" not in link:
        wx_match = WECHAT_LINK_RE.search(item_xml)
        if not wx_match:
            return None
        link = wx_match.group(0).rstrip("\"'<>")

    date_match = re.search(r"\d{4}-\d{2}-\d{2}", title)
    return {
        "title": title,
        "link": link,
        "date": date_match.group() if date_match else "",
    }


def resolve_article_from_rss(target_date=None):
    rss = load_rss_to_html()
    try:
        with urllib.request.urlopen(rss.RSS_URL, timeout=15) as response:
            rss_content = response.read().decode("utf-8")
    except Exception:
        return None

    if target_date:
        item_xml = rss.find_item_by_date(rss_content, target_date)
    else:
        item_match = re.search(r"<item>(.*?)</item>", rss_content, re.DOTALL)
        item_xml = item_match.group(1) if item_match else None

    if not item_xml:
        return None

    return _article_from_rss_item(item_xml)
