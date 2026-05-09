from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .base import PlatformAdapter


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
