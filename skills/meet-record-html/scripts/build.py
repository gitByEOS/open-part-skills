"""面试问题 Markdown → 纪要 HTML 生成器

输入格式见 SKILL.md，输出单文件 HTML（基于 assets/template.html）。
仅依赖 Python 标准库。
"""
import argparse
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "assets" / "template.html"

# ---------- 解析 ----------

QUESTION_RE = re.compile(
    r"""^\s*
        (?P<num>\d+)\.\s*            # 编号
        (?:[（(](?P<tags>[^)）]*)[)）])?  # 可选括号标签，支持中英文括号
        \s*(?P<text>.+?)\s*$         # 问题正文
    """,
    re.VERBOSE,
)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def strip_frontmatter(text):
    """剥掉 YAML 头（若存在），不解析其内容。"""
    m = FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


def parse_meta(md):
    """提取标题、副标题、候选人、时间，仅从正文 # / ## 推导。"""
    title = "面试问题与记录"
    heading = None
    subtitle = ""
    candidate = ""
    interview_time = ""

    h1 = None
    meta_line = None
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        if not h1 and s.startswith("# ") and not s.startswith("## "):
            h1 = s[2:].strip()
            continue
        if s.startswith("## "):
            meta_line = s[3:].strip()
            break

    if not heading:
        heading = h1 or "面试问题与记录"

    if meta_line:
        # 形如 "王璨 - 2026-07-08 10:30:00"
        parts = re.split(r"\s*[-–—]\s*", meta_line, maxsplit=1)
        candidate = parts[0].strip()
        if len(parts) > 1:
            interview_time = parts[1].strip()

    interview_time = trim_seconds(interview_time)

    return {
        "title": title,
        "heading": heading,
        "subtitle": subtitle,
        "candidate": candidate or "候选人",
        "time": interview_time or "待定",
    }


def trim_seconds(t):
    """去掉尾部 :SS，例如 10:30:00 → 10:30。"""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}):\d{2}", t)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return t


def parse_questions(md):
    """逐行解析编号问题，返回 [{num, tags, text}]。"""
    questions = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        m = QUESTION_RE.match(s)
        if not m:
            continue
        tags_raw = m.group("tags") or ""
        tags = [t.strip() for t in re.split(r"[·、,，/|]", tags_raw) if t.strip()]
        questions.append({
            "num": int(m.group("num")),
            "tags": tags,
            "text": m.group("text").strip(),
        })
    questions.sort(key=lambda q: q["num"])
    return questions


# ---------- 渲染 ----------

def esc(s):
    return html.escape(s, quote=False)


def render_tags(tags):
    if not tags:
        return ""
    return "\n".join(f'                        <span class="tag">{esc(t)}</span>' for t in tags)


def render_question(q, index):
    qid = f"Q{index}"
    tags_html = render_tags(q["tags"])
    tags_block = f'<div class="question-tags">\n{tags_html}\n                    </div>' if tags_html else ""
    return f"""            <li class="question-item">
                <div class="question-header">
                    <span class="question-number">{qid}</span>
                    {tags_block}
                </div>
                <div class="question-text">
                    {esc(q["text"])}
                </div>
                <div class="answer-summary-label">📝 总结/评价</div>
                <textarea class="answer-textarea" placeholder="在此输入候选人的回答要点、评价或总结..." data-question="{qid}"></textarea>
            </li>"""


def render_questions(questions):
    return "\n".join(render_question(q, i + 1) for i, q in enumerate(questions))


def render_html(meta, questions):
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    out = (
        tpl
        .replace("{{TITLE}}", esc(meta["title"]))
        .replace("{{HEADING}}", esc(meta["heading"]))
        .replace("{{CANDIDATE_NAME}}", esc(meta["candidate"]))
        .replace("{{INTERVIEW_TIME}}", esc(meta["time"]))
        .replace("{{QUESTIONS}}", render_questions(questions))
    )
    # 副标题为空时整段不渲染
    if meta["subtitle"]:
        out = out.replace("{{SUBTITLE}}", esc(meta["subtitle"]))
    else:
        out = out.replace('\n                <div class="subtitle">{{SUBTITLE}}</div>', "")
        out = out.replace("{{SUBTITLE}}", "")
    return out


# ---------- 主入口 ----------

def read_input(path):
    if path == "-" or not path:
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def default_output(input_path):
    if not input_path or input_path == "-":
        return "/tmp/meet.html"
    p = Path(input_path)
    return str(p.with_suffix(".html"))


def main():
    parser = argparse.ArgumentParser(description="面试问题 Markdown → 纪要 HTML")
    parser.add_argument("input", nargs="?", default="-", help="输入 md 文件路径，- 表示 stdin")
    parser.add_argument("-o", "--output", help="输出 html 路径，默认与输入同目录")
    parser.add_argument("--print-json", action="store_true", help="只打印解析结果，便于排查")
    args = parser.parse_args()

    md = read_input(args.input)
    body = strip_frontmatter(md)
    meta = parse_meta(body)
    questions = parse_questions(body)

    if args.print_json:
        print(json.dumps({"meta": meta, "questions": questions}, ensure_ascii=False, indent=2))
        return

    if not questions:
        print("⚠️  未解析到任何问题，请检查 md 格式（需 `数字. （标签）问题`）", file=sys.stderr)
        sys.exit(1)

    html_out = render_html(meta, questions)
    out_path = args.output or default_output(args.input)
    Path(out_path).write_text(html_out, encoding="utf-8")
    print(f"✅ 已生成：{out_path}（{len(questions)} 题）")


if __name__ == "__main__":
    main()
