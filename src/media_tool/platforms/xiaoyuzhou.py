from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from .base import PlatformAdapter


class XiaoyuzhouPlatformAdapter(PlatformAdapter):
    name = "xiaoyuzhou"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return host.endswith("xiaoyuzhoufm.com")

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        clean = parsed._replace(query="", fragment="")
        return urlunparse(clean)

    def subtitle_languages(self) -> list[str]:
        return ["zh", "en"]
