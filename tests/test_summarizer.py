from __future__ import annotations

import pytest

from src.media_tool.models import MediaSource
from src.media_tool.summarizer import summarize_text
from src.media_tool.utils import SummarizationError


class FakeClient:
    def __init__(self, content: str, should_raise: bool = False) -> None:
        self.content = content
        self.should_raise = should_raise

    def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        if self.should_raise:
            raise RuntimeError("boom")
        return self.content


SOURCE = MediaSource(
    url="https://www.youtube.com/watch?v=abc123",
    normalized_url="https://www.youtube.com/watch?v=abc123",
    platform="youtube",
    title="测试标题",
)


def test_summarize_text_parses_structured_response() -> None:
    client = FakeClient('{"title":"总结标题","summary":"核心总结","topics":["AI"],"key_points":["重点1"],"quotes":["引用1"]}')
    result = summarize_text(SOURCE, "正文", client=client)
    # source.title ("测试标题") takes priority over model response title
    assert result.title == "测试标题"
    assert result.topics == ["AI"]
    assert result.key_points == ["重点1"]
    assert result.quotes == ["引用1"]


def test_summarize_text_uses_model_title_when_source_has_none() -> None:
    source_no_title = MediaSource(
        url="https://www.youtube.com/watch?v=abc123",
        normalized_url="https://www.youtube.com/watch?v=abc123",
        platform="youtube",
        title=None,
    )
    client = FakeClient('{"title":"总结标题","summary":"核心总结","topics":["AI"],"key_points":["重点1"],"quotes":["引用1"]}')
    result = summarize_text(source_no_title, "正文", client=client)
    assert result.title == "总结标题"


def test_summarize_text_rejects_missing_summary() -> None:
    client = FakeClient('{"title":"总结标题"}')
    with pytest.raises(SummarizationError):
        summarize_text(SOURCE, "正文", client=client)


def test_summarize_text_wraps_model_errors() -> None:
    client = FakeClient("{}", should_raise=True)
    with pytest.raises(SummarizationError):
        summarize_text(SOURCE, "正文", client=client)
