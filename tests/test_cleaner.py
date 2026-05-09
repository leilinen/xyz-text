from __future__ import annotations

from src.media_tool.cleaner import clean_transcript_text, split_segments


RAW_TEXT = """WEBVTT

1
00:00:00.000 --> 00:00:02.000 align:start position:0%
<v Speaker>你好，世界。</v>

2
00:00:02.000 --> 00:00:04.000
你好，世界。

3
00:00:04.000 --> 00:00:06.000
这是第二句。
"""


def test_clean_transcript_text_removes_metadata_and_duplicates() -> None:
    cleaned = clean_transcript_text(RAW_TEXT)
    assert cleaned == "你好，世界。\n这是第二句。"


def test_split_segments_merges_short_sentences() -> None:
    text = "这是第一句。 这是第二句。 这是第三句。"
    segments = split_segments(text, segment_length=12, min_sentence_length=5)
    assert segments == ["这是第一句。 这是第二句。", "这是第三句。"]
