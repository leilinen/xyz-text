from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .base import PlatformAdapter


class YouTubePlatformAdapter(PlatformAdapter):
    name = "youtube"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return host.endswith("youtube.com") or host == "youtu.be"

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.netloc.lower() == "youtu.be":
            video_id = parsed.path.lstrip("/")
            parsed = parsed._replace(netloc="www.youtube.com", path="/watch", query=urlencode({"v": video_id}))
        query = parse_qs(parsed.query)
        keep = {}
        if "v" in query:
            keep["v"] = query["v"][0]
        clean = parsed._replace(query=urlencode(keep), fragment="")
        return urlunparse(clean)
