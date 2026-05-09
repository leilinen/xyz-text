from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.media_tool.shownotes import fetch_xiaoyuzhou_shownote, parse_xiaoyuzhou_shownote, strip_timeline


def _page_html(episode: dict) -> str:
    payload = {"props": {"pageProps": {"episode": episode}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>'


def test_strip_timeline_preserves_following_sections() -> None:
    text = """🎤 本期嘉宾
嘉宾介绍

🎯 时间轴
00:21 看山是山
1:02:53 Frequency 频率

📁 本期内容相关资料
* 《凯利公式介绍》

🎬 后期制作
Dong"""

    result = strip_timeline(text)

    assert "🎯 时间轴" not in result
    assert "00:21 看山是山" not in result
    assert "1:02:53 Frequency" not in result
    assert "📁 本期内容相关资料" in result
    assert "《凯利公式介绍》" in result
    assert "🎬 后期制作" in result


def test_parse_xiaoyuzhou_shownote_uses_html_and_images() -> None:
    html = _page_html({
        "shownotes": """
            <p><span>🎤 </span><strong><span>本期嘉宾</span></strong></p>
            <p><span>徐倬迅 | </span><a href="https://example.com/profile"><span>徐倬迅的投资日记</span></a></p>
            <p><span>🎯 时间轴</span></p>
            <p><span>00:21 看山是山</span></p>
            <p><span>03:45 赌神的牌局</span></p>
            <p><span>📁 本期内容相关资料</span></p>
            <p><span>* 《凯利公式介绍》</span></p>
            <p><img src="https://image.xyzcdn.net/chart.png"/></p>
            <p><img src="https://image.xyzcdn.net/chart.png"/></p>
        """,
        "description": "fallback",
    })

    result = parse_xiaoyuzhou_shownote(html)

    assert result is not None
    assert "本期嘉宾" in result.text
    assert "https://example.com/profile" in result.text
    assert "时间轴" not in result.text
    assert "00:21 看山是山" not in result.text
    assert "本期内容相关资料" in result.text
    assert result.images == ["https://image.xyzcdn.net/chart.png"]


def test_parse_xiaoyuzhou_shownote_falls_back_to_description() -> None:
    html = _page_html({
        "description": "简介\n🎯 时间轴\n00:21 不应保留\n📁 资料\n保留资料",
    })

    result = parse_xiaoyuzhou_shownote(html)

    assert result is not None
    assert result.text == "简介\n📁 资料\n保留资料"
    assert result.images == []


@patch("src.media_tool.shownotes.requests.get")
def test_fetch_xiaoyuzhou_shownote_returns_none_without_blocking(mock_get: MagicMock) -> None:
    mock_get.side_effect = RuntimeError("network down")

    assert fetch_xiaoyuzhou_shownote("https://www.xiaoyuzhoufm.com/episode/abc") is None
