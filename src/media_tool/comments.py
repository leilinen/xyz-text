"""Extract and filter hot comments from YouTube, Bilibili, and Xiaoyuzhou."""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

import requests

from .models import Comment, HotCommentsResult

logger = logging.getLogger(__name__)

_MAX_HOT_COMMENTS = 10


def _parse_comment(raw: dict[str, Any]) -> Comment:
    """Parse a single comment from yt-dlp info dict."""
    return Comment(
        author=str(raw.get("author") or ""),
        text=str(raw.get("text") or ""),
        like_count=int(raw.get("like_count") or 0),
        timestamp=int(raw.get("timestamp") or 0),
        is_pinned=bool(raw.get("is_pinned", False)),
        is_creator_favorited=bool(raw.get("is_favorited", False)),
    )


def filter_hot_comments(comments: list[Comment], max_count: int = _MAX_HOT_COMMENTS) -> list[Comment]:
    """Select hot comments: pinned, creator-favorited, and top-liked.

    Rules:
    1. Always include pinned and creator-favorited comments
    2. Fill remaining slots with top-liked comments
    3. Deduplicate by comment text
    """
    special: list[Comment] = []
    rest: list[Comment] = []

    for c in comments:
        if c.is_pinned or c.is_creator_favorited:
            special.append(c)
        else:
            rest.append(c)

    # Sort rest by likes descending
    rest.sort(key=lambda c: c.like_count, reverse=True)

    # Deduplicate by text content
    seen_texts: set[str] = set()
    result: list[Comment] = []

    for c in special + rest:
        if c.text in seen_texts:
            continue
        seen_texts.add(c.text)
        result.append(c)
        if len(result) >= max_count:
            break

    return result


def _fetch_bilibili_comments(url: str, timeout: int = 30) -> HotCommentsResult | None:
    """Fetch hot comments from Bilibili via its comment API directly.

    Uses sort=2 (by hot/popular) to get the most liked comments.
    Unlike yt-dlp, this API returns actual like counts.
    """
    try:
        # Get video AID via yt-dlp metadata
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("yt-dlp metadata fetch failed for Bilibili comments: %s", result.stderr[:200])
            return None

        info = json.loads(result.stdout)
        aid = info.get("aid") or info.get("id")
        if not aid:
            logger.warning("could not determine Bilibili AID")
            return None

        total_count = info.get("comment_count") or 0

        # Fetch hot comments (sort=2 = by popularity)
        all_comments: list[Comment] = []
        for page in range(1, 4):  # fetch up to 3 pages
            resp = requests.get(
                "https://api.bilibili.com/x/v2/reply",
                params={"type": 1, "oid": aid, "sort": 2, "pn": page, "ps": 20},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                logger.warning("Bilibili comment API error: %s", data.get("message"))
                break

            replies = data.get("data", {}).get("replies") or []
            if not replies:
                break

            for r in replies:
                all_comments.append(Comment(
                    author=r.get("member", {}).get("uname", ""),
                    text=r.get("content", {}).get("message", ""),
                    like_count=int(r.get("like", 0)),
                    timestamp=int(r.get("ctime", 0)),
                    is_pinned=False,
                    is_creator_favorited=False,
                ))

        hot = filter_hot_comments(all_comments)
        logger.info("Bilibili: fetched %d comments, %d hot selected", len(all_comments), len(hot))
        return HotCommentsResult(comments=hot, total_count=total_count)

    except Exception as exc:
        logger.warning("failed to fetch Bilibili comments: %s", exc)
        return None


def _fetch_youtube_comments(url: str, timeout: int = 120) -> HotCommentsResult | None:
    """Fetch hot comments from YouTube via yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--write-comments", "--skip-download", url],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("yt-dlp comment fetch failed: %s", result.stderr[:200])
            return None

        info = json.loads(result.stdout)
        raw_comments = info.get("comments") or []
        total_count = info.get("comment_count") or len(raw_comments)

        parsed = [_parse_comment(c) for c in raw_comments]
        hot = filter_hot_comments(parsed)

        logger.info("YouTube: fetched %d comments, %d hot selected", len(parsed), len(hot))
        return HotCommentsResult(comments=hot, total_count=total_count)

    except Exception as exc:
        logger.warning("failed to fetch YouTube comments: %s", exc)
        return None


def _fetch_xiaoyuzhou_comments(url: str, timeout: int = 30) -> HotCommentsResult | None:
    """Fetch hot comments from Xiaoyuzhou by parsing SSR HTML.

    Xiaoyuzhou embeds comments in the page via Next.js __NEXT_DATA__ JSON blob.
    Comments are pre-sorted: pinned first, then by likeCount descending.
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=timeout,
        )
        resp.raise_for_status()

        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            resp.text,
            re.DOTALL,
        )
        if not match:
            logger.warning("no __NEXT_DATA__ found in Xiaoyuzhou page")
            return None

        data = json.loads(match.group(1))
        page_props = data.get("props", {}).get("pageProps", {})
        raw_comments = page_props.get("comments") or []
        total_count = page_props.get("episode", {}).get("commentCount") or len(raw_comments)

        comments: list[Comment] = []
        for c in raw_comments:
            author_info = c.get("author") or {}
            created_at = c.get("createdAt", "")
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ts = int(dt.timestamp())
            except (ValueError, AttributeError):
                ts = 0

            comments.append(Comment(
                author=author_info.get("nickname", ""),
                text=c.get("text", ""),
                like_count=int(c.get("likeCount", 0)),
                timestamp=ts,
                is_pinned=bool(c.get("pinned", False)),
                is_creator_favorited=False,
            ))

        # Already sorted (pinned first, then by likes), just take top N
        hot = comments[:_MAX_HOT_COMMENTS]
        logger.info("Xiaoyuzhou: fetched %d comments, %d hot selected", len(comments), len(hot))
        return HotCommentsResult(comments=hot, total_count=total_count)

    except Exception as exc:
        logger.warning("failed to fetch Xiaoyuzhou comments: %s", exc)
        return None


def fetch_comments(url: str, platform: str, timeout: int = 120) -> HotCommentsResult | None:
    """Fetch and filter hot comments from a video URL.

    Uses platform-specific approach:
    - Bilibili: direct API (includes like counts)
    - YouTube: yt-dlp (includes like counts, is_pinned, is_favorited)
    - Xiaoyuzhou: HTML page scraping (SSR __NEXT_DATA__ JSON)

    Returns None if extraction fails (non-blocking).
    """
    if platform == "bilibili":
        return _fetch_bilibili_comments(url, timeout=timeout)
    elif platform == "youtube":
        return _fetch_youtube_comments(url, timeout=timeout)
    elif platform == "xiaoyuzhou":
        return _fetch_xiaoyuzhou_comments(url, timeout=timeout)
    else:
        logger.info("comment extraction not supported for platform: %s", platform)
        return None
