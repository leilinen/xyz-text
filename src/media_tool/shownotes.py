"""Extract episode shownotes from supported podcast pages."""

from __future__ import annotations

import html
import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

import requests

from .models import ShownoteContent

logger = logging.getLogger(__name__)


class _ShownoteHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.images: list[str] = []
        self._link_stack: list[str | None] = []
        self._last_was_newline = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"p", "div", "section", "ul", "ol"}:
            self._newline()
        elif tag == "br":
            self._newline()
        elif tag == "li":
            self._newline()
            self._append("* ")
        elif tag == "a":
            self._link_stack.append(attrs_dict.get("href"))
        elif tag == "img":
            src = attrs_dict.get("src") or attrs_dict.get("data-src")
            if src:
                self.images.append(html.unescape(src))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            href = self._link_stack.pop() if self._link_stack else None
            if href:
                self._append(f" ({html.unescape(href)})")
        elif tag in {"p", "div", "section", "li", "ul", "ol"}:
            self._newline()

    def handle_data(self, data: str) -> None:
        text = html.unescape(data)
        if text.strip():
            self._append(text)

    def _append(self, text: str) -> None:
        self.parts.append(text)
        self._last_was_newline = False

    def _newline(self) -> None:
        if not self._last_was_newline:
            self.parts.append("\n")
            self._last_was_newline = True

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        compact: list[str] = []
        for line in lines:
            if not line:
                if compact and compact[-1]:
                    compact.append("")
                continue
            compact.append(line)
        return "\n".join(compact).strip()


def _extract_next_data(page_html: str) -> dict[str, Any] | None:
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        page_html,
        re.DOTALL,
    )
    if not match:
        return None
    return json.loads(html.unescape(match.group(1)))


def _extract_jsonld_description(page_html: str) -> str | None:
    match = re.search(
        r'<script name="schema:podcast-show" type="application/ld\+json">(.*?)</script>',
        page_html,
        re.DOTALL,
    )
    if not match:
        return None
    payload = json.loads(html.unescape(match.group(1)))
    description = payload.get("description")
    return str(description) if description else None


def _extract_episode(page_html: str) -> dict[str, Any]:
    data = _extract_next_data(page_html)
    if not data:
        return {}
    episode = data.get("props", {}).get("pageProps", {}).get("episode", {})
    return episode if isinstance(episode, dict) else {}


def _html_to_shownote(content: str) -> ShownoteContent:
    parser = _ShownoteHTMLParser()
    parser.feed(content)
    return ShownoteContent(text=parser.text(), images=_dedupe_urls(parser.images))


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        clean = url.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


_TIMESTAMP_LINE_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\b")


def _is_timeline_heading(line: str) -> bool:
    stripped = line.strip().strip("#").strip()
    return bool(re.search(r"时间轴|timeline", stripped, re.IGNORECASE))


def _is_timestamp_line(line: str) -> bool:
    return bool(_TIMESTAMP_LINE_RE.match(line))


def _is_section_heading(line: str) -> bool:
    stripped = line.strip().strip("#").strip()
    if not stripped or _is_timestamp_line(stripped):
        return False
    if re.match(r"^[^\w\s\d:：]{1,4}\s*\S+", stripped):
        return True
    return bool(re.match(r"^(?:本期|相关|资料|参考|后期|制作|欢迎|嘉宾|简介|风险提示)\b", stripped))


def strip_timeline(text: str) -> str:
    """Remove the timeline section while preserving following shownote sections."""
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False

    for line in lines:
        if not skipping and _is_timeline_heading(line):
            skipping = True
            continue

        if skipping:
            if _is_section_heading(line) and not _is_timeline_heading(line):
                skipping = False
            else:
                continue

        kept.append(line)

    return "\n".join(kept).strip()


def parse_xiaoyuzhou_shownote(page_html: str) -> ShownoteContent | None:
    """Parse Xiaoyuzhou shownotes from SSR HTML and drop timeline entries."""
    episode = _extract_episode(page_html)
    raw_shownotes = episode.get("shownotes")

    if isinstance(raw_shownotes, str) and raw_shownotes.strip():
        parsed = _html_to_shownote(raw_shownotes)
    else:
        description = episode.get("description")
        if not isinstance(description, str) or not description.strip():
            description = _extract_jsonld_description(page_html)
        if not description:
            return None
        parsed = ShownoteContent(text=description.strip(), images=[])

    text = strip_timeline(parsed.text)
    if not text and not parsed.images:
        return None
    return ShownoteContent(text=text, images=parsed.images)


def fetch_xiaoyuzhou_shownote(url: str, timeout: int = 30) -> ShownoteContent | None:
    """Fetch Xiaoyuzhou shownotes from SSR HTML.

    Failures are non-blocking for the media pipeline.
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return parse_xiaoyuzhou_shownote(resp.text)
    except Exception as exc:
        logger.warning("failed to fetch Xiaoyuzhou shownote: %s", exc)
        return None
