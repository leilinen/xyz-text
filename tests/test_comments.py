from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.media_tool.comments import (
    _fetch_xiaoyuzhou_comments,
    _parse_comment,
    filter_hot_comments,
    fetch_comments,
)
from src.media_tool.models import Comment


def _make_comment(
    text: str = "test",
    author: str = "user",
    like_count: int = 0,
    is_pinned: bool = False,
    is_creator_favorited: bool = False,
) -> Comment:
    return Comment(
        author=author,
        text=text,
        like_count=like_count,
        timestamp=1000,
        is_pinned=is_pinned,
        is_creator_favorited=is_creator_favorited,
    )


def test_filter_top_likes():
    comments = [_make_comment(text=f"comment {i}", like_count=i * 10) for i in range(20)]
    result = filter_hot_comments(comments)
    assert len(result) == 10
    # Should be sorted by like_count descending
    assert result[0].text == "comment 19"
    assert result[0].like_count == 190
    assert result[-1].like_count == 100


def test_filter_includes_pinned():
    comments = [
        _make_comment(text="pinned", like_count=0, is_pinned=True),
        _make_comment(text="popular", like_count=999),
    ] + [_make_comment(text=f"c{i}", like_count=100 - i) for i in range(10)]
    result = filter_hot_comments(comments)
    texts = [c.text for c in result]
    assert "pinned" in texts


def test_filter_includes_creator_favorited():
    comments = [
        _make_comment(text="hearted", like_count=0, is_creator_favorited=True),
        _make_comment(text="popular", like_count=999),
    ] + [_make_comment(text=f"c{i}", like_count=100 - i) for i in range(10)]
    result = filter_hot_comments(comments)
    texts = [c.text for c in result]
    assert "hearted" in texts


def test_filter_deduplicates():
    comments = [
        _make_comment(text="same", like_count=100),
        _make_comment(text="same", like_count=50),
    ]
    result = filter_hot_comments(comments)
    assert len(result) == 1
    assert result[0].like_count == 100


def test_filter_respects_max_count():
    comments = [_make_comment(text=f"c{i}", like_count=i) for i in range(20)]
    result = filter_hot_comments(comments, max_count=5)
    assert len(result) == 5


def test_parse_comment():
    raw = {
        "author": "Alice",
        "text": "Great video!",
        "like_count": 42,
        "timestamp": 1700000000,
        "is_pinned": True,
        "is_favorited": False,
    }
    c = _parse_comment(raw)
    assert c.author == "Alice"
    assert c.text == "Great video!"
    assert c.like_count == 42
    assert c.is_pinned is True
    assert c.is_creator_favorited is False


def test_parse_comment_missing_fields():
    c = _parse_comment({})
    assert c.author == ""
    assert c.text == ""
    assert c.like_count == 0
    assert c.is_pinned is False
    assert c.is_creator_favorited is False


# --- Xiaoyuzhou comment tests ---

_SAMPLE_NEXT_DATA = """
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "episode": {"commentCount": 132},
      "comments": [
        {
          "id": "c1",
          "type": "COMMENT",
          "author": {"nickname": "Alice", "uid": "u1"},
          "text": "Pinned comment",
          "likeCount": 5,
          "createdAt": "2026-03-28T14:10:14.976Z",
          "pinned": true
        },
        {
          "id": "c2",
          "type": "COMMENT",
          "author": {"nickname": "Bob", "uid": "u2"},
          "text": "Top liked comment",
          "likeCount": 214,
          "createdAt": "2026-03-28T15:00:00.000Z",
          "pinned": false
        },
        {
          "id": "c3",
          "type": "COMMENT",
          "author": {"nickname": "Charlie", "uid": "u3"},
          "text": "Another comment",
          "likeCount": 64,
          "createdAt": "2026-03-28T16:00:00.000Z",
          "pinned": false
        }
      ]
    }
  }
}
</script>
"""


@patch("src.media_tool.comments.requests.get")
def test_xiaoyuzhou_parses_comments(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = _SAMPLE_NEXT_DATA
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = _fetch_xiaoyuzhou_comments("https://www.xiaoyuzhoufm.com/episode/abc123")
    assert result is not None
    assert result.total_count == 132
    assert len(result.comments) == 3

    # First comment is pinned
    assert result.comments[0].is_pinned is True
    assert result.comments[0].author == "Alice"
    assert result.comments[0].like_count == 5

    # Second comment is top liked
    assert result.comments[1].author == "Bob"
    assert result.comments[1].like_count == 214
    assert result.comments[1].is_pinned is False


@patch("src.media_tool.comments.requests.get")
def test_xiaoyuzhou_truncates_to_max(mock_get):
    import json

    comments_json = [
        {
            "id": f"c{i}",
            "type": "COMMENT",
            "author": {"nickname": f"user{i}"},
            "text": f"comment {i}",
            "likeCount": 100 - i,
            "createdAt": "2026-03-28T14:10:14.976Z",
            "pinned": False,
        }
        for i in range(20)
    ]
    next_data = json.dumps({
        "props": {"pageProps": {"episode": {"commentCount": 20}, "comments": comments_json}}
    })
    page_html = f'<script id="__NEXT_DATA__" type="application/json">{next_data}</script>'
    mock_resp = MagicMock()
    mock_resp.text = page_html
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = _fetch_xiaoyuzhou_comments("https://www.xiaoyuzhoufm.com/episode/abc")
    assert result is not None
    assert len(result.comments) == 10


@patch("src.media_tool.comments.requests.get")
def test_xiaoyuzhou_no_next_data(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = "<html><body>No data here</body></html>"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = _fetch_xiaoyuzhou_comments("https://www.xiaoyuzhoufm.com/episode/abc")
    assert result is None


def test_fetch_comments_dispatches_xiaoyuzhou():
    with patch("src.media_tool.comments._fetch_xiaoyuzhou_comments") as mock:
        mock.return_value = None
        fetch_comments("https://www.xiaoyuzhoufm.com/episode/abc", platform="xiaoyuzhou")
        mock.assert_called_once()


def test_fetch_comments_unknown_platform():
    result = fetch_comments("https://example.com/video/123", platform="unknown")
    assert result is None
