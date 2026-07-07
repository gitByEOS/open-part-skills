"""blog-narrator flow:parse_md → {export_preview | split → gen → match → merge}。

单 flow 双路径,由节点 accept 按 self.kwargs["mode"] 跳过:
- preview:parse_md → export_preview(TTS 链全 skip)
- tts:parse_md → split → gen → match(条件) → merge(export_preview skip)

match 为条件节点:audio/ 存在非 N.mp3 命名文件时才跑,否则 accept False 跳过,
merge 直读 gen.audio_dir 不依赖 match artifact。无 TO_AGENT 断点,一次跑完。
"""

from esflow import flow, edge


@flow(id="blog-narrator", title="博客逐行披露演示 + 分段配音")
class BlogNarratorFlow:
    nodes = ["parse_md", "export_preview", "split", "gen", "match", "merge"]
    edges = [
        edge("parse_md", "export_preview"),
        edge("parse_md", "split"),
        edge("split", "gen"),
        edge("gen", "match"),
        edge("match", "merge"),
    ]
