#!/usr/bin/env python3
"""把记忆卡 JSON 校验后导出成单文件钉纸网页"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FIELDS = ("title", "desc", "point", "full")
HAN_THEME = re.compile(r"[\u4e00-\u9fff]{2,8}")
CN_DIGITS = "零一二三四五六七八九"


def fail(index, message):
    """校验失败时指出卡片序号并退出"""
    where = f"第 {index} 张" if index else "文档"
    sys.exit(f"错误：{where}：{message}")


def chinese_number(value):
    """1–99 转中文段落序"""
    if not 1 <= value <= 99:
        raise ValueError(value)
    if value < 10:
        return CN_DIGITS[value]
    tens, ones = divmod(value, 10)
    head = "十" if tens == 1 else CN_DIGITS[tens] + "十"
    return head if ones == 0 else head + CN_DIGITS[ones]


def require_text(card, index):
    """四字段都必须是非空字符串"""
    if not isinstance(card, dict):
        fail(index, "卡片必须是对象")
    for key in FIELDS:
        value = card.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(index, f"{key} 必须是非空字符串")
        card[key] = value.strip()


def check_title(title, index):
    """段落序对上卡片顺序，主题 2–8 个汉字"""
    prefix = f"段落{chinese_number(index)} · "
    if not title.startswith(prefix):
        fail(index, f"title 应为「{prefix}主题」")
    theme = title[len(prefix):]
    if HAN_THEME.fullmatch(theme) is None:
        fail(index, "主题须为 2–8 个汉字")


def anchors_of(point, index):
    """按点串切开串联点，点只作分隔"""
    anchors = []
    cursor = 0
    while cursor < len(point):
        if point[cursor] == ".":
            end = cursor + 1
            while end < len(point) and point[end] == ".":
                end += 1
            length = end - cursor
            if length < 3 or length > 6:
                fail(index, f"点串长度是 {length}，只允许 3–6 个点")
            cursor = end
            continue
        end = point.find(".", cursor)
        if end < 0:
            end = len(point)
        word = point[cursor:end]
        if len(word) > 4:
            fail(index, f"锚点「{word}」超过 4 字")
        if not any("\u4e00" <= char <= "\u9fff" for char in word):
            fail(index, f"锚点「{word}」里没有汉字")
        anchors.append(word)
        cursor = end
    if not anchors:
        fail(index, "串联点里没有锚点")
    return anchors


def locate_anchors(full, anchors, index):
    """锚点按顺序、不重叠地落在原文里"""
    pos = 0
    for word in anchors:
        found = full.find(word, pos)
        if found < 0:
            fail(index, f"锚点「{word}」没有按顺序出现在原文里")
        pos = found + len(word)


def check_desc(desc, anchors, index):
    """概述各项都从锚点里取，是某个锚点的连续子串"""
    parts = [part.strip() for part in desc.split("、")]
    if any(not part for part in parts):
        fail(index, "概述有空项")
    for part in parts:
        if not any(part in anchor for anchor in anchors):
            fail(index, f"概述「{part}」不在串联锚点里")


def validate(data):
    """校验课文名和每一张卡，通过后返回原对象"""
    if not isinstance(data, dict):
        fail(0, "根必须是对象")
    title = data.get("title")
    cards = data.get("cards")
    if not isinstance(title, str) or not title.strip():
        fail(0, "title 必须是非空字符串")
    if not isinstance(cards, list) or not cards:
        fail(0, "cards 至少一张")
    data["title"] = title.strip()
    for index, card in enumerate(cards, start=1):
        try:
            chinese_number(index)
        except ValueError:
            fail(index, "段落序只支持到九十九")
        require_text(card, index)
        check_title(card["title"], index)
        anchors = anchors_of(card["point"], index)
        check_desc(card["desc"], anchors, index)
        locate_anchors(card["full"], anchors, index)
    return data


def render(data, footer):
    """读模板与静态资源，内联为单文件 HTML"""
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    css = (ASSETS / "board.css").read_text(encoding="utf-8")
    js = (ASSETS / "board.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    parts = {
        "TITLE": html.escape(data["title"]),
        "CSS": css,
        "JS": js,
        "DATA": payload,
        "FOOTER": html.escape(footer),
    }
    return re.sub(
        r"\{\{(TITLE|CSS|JS|DATA|FOOTER)\}\}",
        lambda match: parts[match.group(1)],
        template,
    )


def load_cards(src):
    """读取并校验 JSON"""
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"错误：JSON 无法解析：{exc}")
    return validate(data)


def main():
    parser = argparse.ArgumentParser(description="记忆卡 JSON → 钉纸网页")
    parser.add_argument("input", help="输入 JSON 文件")
    parser.add_argument("-o", "--output", help="输出 HTML 路径")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.is_file():
        sys.exit(f"错误：文件不存在 {src}")
    data = load_cards(src)
    out = Path(args.output) if args.output else src.with_suffix(".html")
    if out.resolve() == src.resolve():
        sys.exit("错误：输出路径不能和输入 JSON 相同")
    footer = f"源文件 {src.name}"
    out.write_text(render(data, footer), encoding="utf-8")
    print(f"已生成 {out}（卡片 {len(data['cards'])}）")


if __name__ == "__main__":
    main()
