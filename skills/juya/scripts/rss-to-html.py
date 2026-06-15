#!/usr/bin/env python3
"""
解析橘鸦Juya RSS，输出分页 HTML —— 早茶早报风格
"""

import urllib.request
import re
import os
import sys
from datetime import datetime
import html as html_mod

RSS_URL = "https://daily.juya.uk/rss.xml"

# 字体栈
FONT_BODY = "'Noto Serif CJK SC', 'Source Han Serif SC', 'Songti SC', 'STSong', 'SimSun', serif"
FONT_HEADING = "'STKaiti', 'Kaiti SC', 'Noto Serif CJK SC', serif"
FONT_EN = "'Crimson Pro', 'Georgia', 'Times New Roman', serif"


def parse_sections(html_content):
    """按 h2 切分为若干节，返回 [(title, body_html), ...]"""
    if not html_content.strip():
        return [("正文", "")]

    parts = re.split(r'(<h2[^>]*>.*?</h2>)', html_content, flags=re.DOTALL)

    sections = []
    # 前导内容（概览等）
    if parts[0].strip():
        leading = parts[0].strip()
        ol_match = re.search(r'<h[12][^>]*>(.*?)</h[12]>', leading, re.DOTALL)
        overview_title = re.sub(r'<[^>]+>', '', ol_match.group(1)).strip() if ol_match else "概览"
        sections.append((overview_title, leading))

    i = 1
    while i < len(parts):
        title_html = parts[i] if i < len(parts) else ""
        title_clean = re.sub(r'<[^>]+>', '', title_html).strip()
        if not title_clean:
            title_clean = "其他"
        body = ""
        if i + 1 < len(parts):
            body = parts[i + 1].strip()
            i += 2
        else:
            i += 1
        if title_clean and (body or title_html):
            sections.append((title_clean, body))

    if not sections:
        sections.append(("正文", html_content))

    return sections


def section_css():
    return f"""
    @import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,300;0,400;0,600;0,700;1,400&family=Noto+Serif+SC:wght@400;600;700&display=swap');

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    html {{ scroll-behavior: smooth; }}

    body {{
      font-family: {FONT_EN}, {FONT_BODY};
      font-size: 16px;
      line-height: 1.85;
      color: #2a2a2a;
      background: #ede7db;
    }}

    /* ── 顶部固定目录条 ── */
    .toc-bar {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 100;
      background: rgba(44,36,22,0.95);
      backdrop-filter: blur(6px);
      padding: 0;
      border-bottom: 1px solid rgba(200,180,150,0.3);
    }}

    .toc-inner {{
      max-width: 900px;
      margin: 0 auto;
      padding: 10px 30px;
      display: flex;
      align-items: center;
      gap: 8px;
      overflow-x: auto;
      scrollbar-width: none;
    }}

    .toc-inner::-webkit-scrollbar {{ display: none; }}

    .toc-brand {{
      font-family: {FONT_HEADING};
      font-size: 0.95em;
      color: #e8e0d0;
      white-space: nowrap;
      margin-right: 12px;
      letter-spacing: 0.1em;
      text-decoration: none;
      cursor: pointer;
      transition: color 0.15s ease;
    }}

    .toc-brand:hover {{
      color: #f5f0e6;
    }}

    .toc-divider {{
      color: #6b5b4a;
      font-size: 0.7em;
      user-select: none;
    }}

    .toc-link {{
      white-space: nowrap;
      padding: 4px 14px;
      background: rgba(255,255,255,0.08);
      border-radius: 3px;
      color: #c4b49a;
      text-decoration: none;
      font-size: 0.78em;
      font-family: {FONT_HEADING};
      transition: all 0.15s ease;
      border: 1px solid transparent;
    }}

    .toc-link:hover {{
      background: rgba(255,255,255,0.15);
      color: #f5f0e6;
      border-color: rgba(200,180,150,0.3);
    }}

    .toc-link.active {{
      background: rgba(181,68,58,0.35);
      color: #fff;
      border-color: rgba(181,68,58,0.5);
    }}

    /* ── 封面横幅 ── */
    .cover {{
      padding: 80px 30px 35px;
      text-align: center;
      position: relative;
      border-bottom: 3px double #c4b49a;
      background: linear-gradient(180deg, #ede7db 0%, #e8e0d0 100%);
    }}

    .cover-brand {{
      font-family: {FONT_HEADING};
      font-size: 2.8em;
      font-weight: 700;
      color: #2c2416;
      letter-spacing: 0.18em;
      margin-bottom: 8px;
    }}

    .cover-subtitle {{
      font-family: {FONT_HEADING};
      font-size: 1em;
      color: #8b7355;
      letter-spacing: 0.5em;
      margin-bottom: 18px;
    }}

    .cover-date {{
      font-size: 0.9em;
      color: #6b5b4a;
      letter-spacing: 0.1em;
      padding: 6px 24px;
      border-top: 1px solid #c4b49a;
      border-bottom: 1px solid #c4b49a;
      display: inline-block;
    }}

    .cover-stamp {{
      position: absolute;
      top: 90px;
      right: 18%;
      width: 110px;
      height: 110px;
      border: 3px solid #b5443a;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Ma Shan Zheng', 'STKaiti', 'Kaiti SC', serif;
      font-size: 1.5em;
      color: #a33226;
      transform: rotate(-12deg);
      opacity: 0.8;
      line-height: 1.3;
      text-align: center;
      text-shadow:
        0 0 1px rgba(181,68,58,0.6),
        0.5px 0 0 rgba(181,68,58,0.3),
        -0.5px 0 0 rgba(181,68,58,0.3);
    }}

    .cover-video {{
      margin-top: 20px;
    }}

    .cover-video a {{
      display: inline-block;
      padding: 6px 20px;
      margin: 0 5px;
      background: rgba(181,68,58,0.06);
      border: 1px solid #b5443a;
      border-radius: 3px;
      color: #8b4513;
      text-decoration: none;
      font-size: 0.85em;
      font-family: {FONT_HEADING};
      transition: all 0.15s ease;
    }}

    .cover-video a:hover {{
      background: #b5443a;
      color: #fff;
    }}

    /* ── 章节 ── */
    .sections-wrapper {{
      max-width: 800px;
      margin: 0 auto;
      padding: 15px 30px 60px;
    }}

    .section-block {{
      background: #fffdf8;
      border: 1px solid #e0d6c4;
      border-radius: 5px;
      margin: 0 0 30px;
      box-shadow: 0 2px 8px rgba(60,40,20,0.06);
      scroll-margin-top: 75px;
    }}

    .section-block.toc-active {{
      border-color: #b5443a;
      box-shadow: 0 2px 16px rgba(181,68,58,0.1);
    }}

    .section-header {{
      padding: 22px 35px 18px;
      border-bottom: 1px solid #e8e0d0;
      text-align: center;
      background: linear-gradient(180deg, #faf7f0 0%, #fffdf8 100%);
    }}

    .section-title {{
      font-family: {FONT_HEADING};
      font-size: 1.5em;
      font-weight: 600;
      color: #2c2416;
      letter-spacing: 0.2em;
    }}

    .section-body {{
      padding: 25px 35px 30px;
    }}

    /* 内容排版 */
    .section-body p {{
      margin: 12px 0;
      line-height: 1.95;
      color: #2a2a2a;
    }}

    .section-body a {{
      color: #8b6914;
      text-decoration: none;
      border-bottom: 1px dotted #c4a84a;
      transition: color 0.15s;
    }}

    .section-body a:hover {{
      color: #b5443a;
      border-bottom-color: #b5443a;
    }}

    .section-body h3 {{
      font-family: {FONT_HEADING};
      font-size: 1.1em;
      font-weight: 700;
      color: #b5443a;
      margin: 25px 0 12px;
      padding-left: 14px;
      border-left: 3px solid #b5443a;
      line-height: 1.6;
    }}

    .section-body ul {{
      list-style: none;
      padding: 0;
      margin: 10px 0;
    }}

    .section-body li {{
      display: flex;
      align-items: baseline;
      gap: 10px;
      padding: 10px 14px;
      margin: 6px 0;
      background: #faf7f0;
      border-left: 3px solid #d4c5a9;
      border-radius: 0 3px 3px 0;
      line-height: 1.75;
      transition: background 0.15s;
    }}

    .section-body li:hover {{
      background: #f5f0e4;
    }}

    .section-body li::before {{
      content: "◆";
      flex-shrink: 0;
      color: #b5443a;
      font-size: 0.5em;
      line-height: 1;
      transform: translateY(-0.08em);
    }}

    .section-body li a {{
      font-weight: 600;
    }}

    .section-body ul.ref-links {{
      list-style: none;
      padding: 12px 16px;
      margin: 16px 0;
      background: #faf7f0;
      border-left: 3px solid #d4c5a9;
      border-radius: 0 3px 3px 0;
    }}

    .section-body ul.ref-links li {{
      display: block;
      padding: 5px 0;
      margin: 0;
      background: none;
      border: none;
      border-radius: 0;
      line-height: 1.7;
    }}

    .section-body ul.ref-links li::before {{
      content: none;
      display: none;
    }}

    .section-body ul.ref-links li:hover {{
      background: none;
    }}

    .section-body ul.ref-links a {{
      font-weight: normal;
      word-break: break-all;
    }}

    .section-body p.ref-link {{
      margin: 12px 0;
      padding: 10px 14px;
      background: #faf7f0;
      border-left: 3px solid #d4c5a9;
      border-radius: 0 3px 3px 0;
      line-height: 1.7;
    }}

    .section-body p.ref-link a {{
      word-break: break-all;
      font-weight: normal;
    }}

    .section-body code {{
      background: #e8e0d0;
      padding: 3px 9px;
      border-radius: 3px;
      font-size: 0.82em;
      font-weight: 600;
      color: #4a7ca8;
      font-family: 'Courier New', 'Crimson Pro', monospace;
      border: 1px solid #d4c5a9;
      letter-spacing: 0.02em;
      word-break: break-word;
      vertical-align: baseline;
      line-height: 1.6;
    }}

    .section-body blockquote {{
      background: #faf7f0;
      border-left: 4px solid #c4b49a;
      padding: 18px 22px;
      margin: 18px 0;
      font-style: italic;
      color: #5a4a3a;
      border-radius: 0 3px 3px 0;
    }}

    .section-body blockquote::before {{
      content: '"';
      font-size: 2em;
      color: #c4b49a;
      float: left;
      margin-right: 6px;
      line-height: 1;
      font-family: Georgia, serif;
    }}

    .section-body blockquote p {{
      margin: 0;
    }}

    .section-body blockquote strong {{
      color: #3a2e22;
    }}

    /* 图片 */
    .section-body img {{
      display: block;
      max-width: 100%;
      max-height: 420px;
      object-fit: contain;
      margin: 18px auto;
      border-radius: 3px;
      box-shadow: 0 2px 6px rgba(60,40,20,0.1);
    }}

    .section-body hr {{
      border: none;
      height: 1px;
      background: linear-gradient(to right, transparent, #d4c5a9, transparent);
      margin: 30px 0;
    }}

    /* ── 页脚 ── */
    .footer {{
      background: #2c2416;
      color: #e8e0d0;
      padding: 40px 30px;
      text-align: center;
      font-family: {FONT_HEADING};
    }}

    .footer-quote {{
      font-size: 1.1em;
      font-style: italic;
      margin-bottom: 14px;
      color: #c4b49a;
    }}

    .footer-quote a {{
      color: #c4b49a;
      text-decoration: none;
      border-bottom: 1px dotted #8b7355;
      transition: color 0.15s ease;
    }}

    .footer-quote a:hover {{
      color: #f5f0e6;
    }}

    .footer a {{
      color: #d4c5a9;
      text-decoration: none;
      border-bottom: 1px dotted #8b7355;
    }}

    .footer a:hover {{
      color: #f5f0e6;
    }}

    .footer-info {{
      font-size: 0.82em;
      color: #8b7355;
      margin-top: 6px;
    }}

    /* 封面图单独处理 */
    .cover-image {{
      max-width: 700px;
      margin: 0 auto 20px;
    }}

    .cover-image img {{
      max-width: 100%;
      border-radius: 4px;
      box-shadow: 0 3px 12px rgba(60,40,20,0.12);
    }}

    /* ── 响应式 ── */
    @media (max-width: 640px) {{
      .cover-brand {{ font-size: 2.2em; }}
      .cover-stamp {{ width: 80px; height: 80px; font-size: 1.1em; font-weight: 900; right: 12%; top: 40px; }}
      .toc-inner {{ padding: 8px 15px; }}
      .section-header {{ padding: 16px 20px 14px; }}
      .section-body {{ padding: 18px 20px 22px; }}
      .toc-brand {{ font-size: 0.82em; }}
      .toc-link {{ padding: 3px 10px; font-size: 0.72em; }}
    }}

    @media print {{
      .toc-bar {{ display: none; }}
      body {{ background: #fff; }}
      .section-block {{ box-shadow: none; border: 1px solid #ccc; }}
    }}
    """


def render_cover(title, date_str, issue_no):
    stamp_text = f"第{issue_no}期" if issue_no else date_str.replace('-', '.')
    return f"""
  <div class="cover">
    <div class="cover-stamp">{stamp_text}</div>
    <div class="cover-brand">橘鸦AI早报</div>
    <div class="cover-subtitle">每 日 清 晨 资 讯 速 递</div>
    <div class="cover-date">{date_str}</div>
    <div class="cover-video">
      <a href="https://www.bilibili.com/video/BV1n77f6mE9m">哔哩哔哩</a>
      <a href="https://www.youtube.com/watch?v=ok0DhfYrYdE">YouTube</a>
    </div>
  </div>
    """


def render_section(section_title, section_body, idx):
    return f"""
  <div class="section-block" id="section-{idx}">
    <div class="section-header">
      <h2 class="section-title">{section_title}</h2>
    </div>
    <div class="section-body">
      {section_body}
    </div>
  </div>
    """


def render_footer(source_label="橘鸦Juya AI早报 RSS", source_link=RSS_URL, source_link_text="RSS订阅"):
    return f"""
  <div class="footer">
    <p class="footer-quote">本页面由 <a href="https://github.com/gitByEOS/open-part-skills" target="_blank">EOS.juya skill</a> 生成</p>
    <p class="footer-info">
      来源：{source_label} |
      <a href="https://space.bilibili.com/285286947">B站主页</a> |
      <a href="{html_mod.escape(source_link)}">{source_link_text}</a>
    </p>
    <p class="footer-info" style="margin-top:8px; font-size:0.78em;">
      内容由AI辅助创作，可能存在幻觉和错误，请以原始出处为准
    </p>
  </div>
    """


def render_toc_script():
    return """
  <script>
  (function() {
    var links = document.querySelectorAll('.toc-link');
    var blocks = document.querySelectorAll('.section-block');
    var bar = document.querySelector('.toc-inner');

    if (!links.length || !bar) return;

    links.forEach(function(link) {
      link.addEventListener('click', function(e) {
        link.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      });
    });

    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        var idx = entry.target.id.split('-')[1];
        var link = document.querySelector('.toc-link[href="#section-' + idx + '"]');
        if (!link) return;
        if (entry.isIntersecting) {
          links.forEach(function(l) { l.classList.remove('active'); });
          link.classList.add('active');
          link.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
      });
    }, { rootMargin: '-56px 0px -60% 0px', threshold: 0 });

    blocks.forEach(function(block) { observer.observe(block); });
  })();
  </script>
    """


def render_item_html(item_xml, source_label=None, source_link=None, source_link_text=None):
    """将单个 RSS item XML 渲染为早茶风格 HTML 全文"""
    if source_label is None:
        source_label = "橘鸦Juya AI早报 RSS"
        source_link = RSS_URL
        source_link_text = "RSS订阅"

    title, issue_no, html_content, date_str = extract_item_fields(item_xml)
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    sections = parse_sections(html_content)
    if len(sections) > 1:
        sections = sections[1:]

    toc_items = ""
    for idx, (sec_title, _) in enumerate(sections):
        toc_items += f'<a class="toc-link" href="#section-{idx}">{sec_title}</a>\n'

    body_parts = [render_cover(title, date_str, issue_no)]
    body_parts.append(
        f'<div class="toc-bar"><div class="toc-inner">'
        f'<a class="toc-brand" href="https://github.com/gitByEOS/open-part-skills" target="_blank">EOS.Skill</a>'
        f'<span class="toc-divider">│</span>{toc_items}</div></div>'
    )
    body_parts.append('<div class="sections-wrapper">')
    for idx, (sec_title, sec_body) in enumerate(sections):
        body_parts.append(render_section(sec_title, sec_body, idx))
    body_parts.append('</div>')
    body_parts.append(render_footer(source_label, source_link, source_link_text))
    body_parts.append(render_toc_script())

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>橘鸦AI早报 {date_str}</title>
  <style>
    {section_css()}
  </style>
</head>
<body>
  {''.join(body_parts)}
</body>
</html>"""


def find_item_by_date(rss_content, target_date):
    """在 RSS 中找到指定日期的 item，返回该 item 的 XML 片段"""
    items = re.findall(r'<item>(.*?)</item>', rss_content, re.DOTALL)
    for item in items:
        title = re.search(r'<title>([^<]+)</title>', item)
        if title and target_date in title.group(1):
            return item
    return None


def extract_item_fields(item_xml):
    """从单个 item XML 中提取 title, link(issue_no), content, date"""
    title = ""
    issue_no = ""
    html_content = ""
    date_str = ""

    title_match = re.search(r'<title>([^<]+)</title>', item_xml)
    if title_match:
        title = title_match.group(1)
        date_m = re.search(r'\d{4}-\d{2}-\d{2}', title)
        if date_m:
            date_str = date_m.group()

    link_match = re.search(r'<link>[^<]*issue[-_](\d+)[^<]*</link>', item_xml)
    if link_match:
        issue_no = link_match.group(1)

    content_match = re.search(r'<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>', item_xml, re.DOTALL)
    if content_match:
        html_content = content_match.group(1)

    return title, issue_no, html_content, date_str


def main():
    import argparse
    parser = argparse.ArgumentParser(description='解析橘鸦Juya RSS，输出分页 HTML')
    parser.add_argument('output_dir', nargs='?', default='./juya-output', help='输出目录 (默认 ./juya-output)')
    parser.add_argument('--date', '-d', help='指定日期 YYYY-MM-DD (默认最新一期)')
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # 抓取 RSS
    print("抓取 RSS...")
    with urllib.request.urlopen(RSS_URL) as response:
        rss_content = response.read().decode('utf-8')

    # 解析
    print("解析 RSS...")

    if args.date:
        item_xml = find_item_by_date(rss_content, args.date)
        if not item_xml:
            print(f"❌ 未找到 {args.date} 的早报，请在 RSS 中确认是否存在")
            sys.exit(1)
        print(f"找到 {args.date} 的早报")
    else:
        # 取第一个 item（最新一期）
        item_match = re.search(r'<item>(.*?)</item>', rss_content, re.DOTALL)
        if not item_match:
            print("❌ RSS 中无可用内容")
            sys.exit(1)
        item_xml = item_match.group(1)

    _, _, _, date_str = extract_item_fields(item_xml)
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    full_html = render_item_html(item_xml)

    output_file = os.path.join(output_dir, f"juya-{date_str}.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"✅ 生成完成: {output_file}")

    import subprocess
    import platform
    opener = 'open' if platform.system() == 'Darwin' else 'xdg-open'
    subprocess.run([opener, output_file])


if __name__ == "__main__":
    main()
