from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from .base import PlatformAdapter

logger = logging.getLogger(__name__)

_BV_PATTERN = re.compile(r"(BV[\w]+)")


class BilibiliPlatformAdapter(PlatformAdapter):
    name = "bilibili"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "bilibili.com" in host or host == "b23.tv"

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        query = parse_qs(parsed.query)
        keep = {}
        if "p" in query:
            keep["p"] = query["p"][0]
        clean = parsed._replace(query=urlencode(keep), fragment="")
        return urlunparse(clean)

    def _resolve_bv_id(self, url: str) -> str | None:
        """Extract BV ID from URL, following b23.tv redirects if needed."""
        parsed = urlparse(url.strip())
        # Direct bilibili.com URL — extract from path
        if "bilibili.com" in parsed.netloc:
            m = _BV_PATTERN.search(parsed.path)
            return m.group(1) if m else None
        # b23.tv short link — follow redirect to get full URL
        try:
            resp = requests.head(url.strip(), allow_redirects=True, timeout=10)
            resolved = resp.url
            logger.info("b23.tv resolved: %s -> %s", url, resolved)
            m = _BV_PATTERN.search(resolved)
            return m.group(1) if m else None
        except Exception:
            return None

    def normalize_collection_url(self, url: str) -> str:
        """Resolve to base BV URL without ?p= so yt-dlp sees the full collection."""
        bv_id = self._resolve_bv_id(url)
        if bv_id:
            return f"https://www.bilibili.com/video/{bv_id}"
        return self.normalize_url(url)
