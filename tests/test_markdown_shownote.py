from __future__ import annotations

from src.media_tool.markdown import build_markdown
from src.media_tool.models import MediaSource, ProcessResult, ShownoteContent, SummaryResult


def test_build_markdown_includes_shownote_text_and_images() -> None:
    result = ProcessResult(
        source=MediaSource(
            url="https://www.xiaoyuzhoufm.com/episode/abc",
            normalized_url="https://www.xiaoyuzhoufm.com/episode/abc",
            platform="xiaoyuzhou",
            title="测试节目",
            metadata={"description": "节目简介"},
        ),
        transcript_source="asr",
        transcript="转录全文",
        segments=["转录全文"],
        summary=SummaryResult(
            title="测试节目",
            summary="总结",
            topics=[],
            key_points=[],
            quotes=[],
        ),
        feishu=None,
        shownote=ShownoteContent(
            text="本期内容相关资料\n* 《凯利公式介绍》",
            images=["https://image.xyzcdn.net/chart.png"],
        ),
    )

    markdown = build_markdown(result)

    assert "## 节目介绍" in markdown
    assert "## Shownote" in markdown
    assert "本期内容相关资料" in markdown
    assert "![](https://image.xyzcdn.net/chart.png)" in markdown
    assert markdown.index("## 节目介绍") < markdown.index("## Shownote") < markdown.index("## 总结")
