from __future__ import annotations

import pytest

from src.media_tool.platforms.base import PlatformAdapter
from src.media_tool.platforms.registry import PlatformRegistry, resolve_platform
from src.media_tool.utils import UnsupportedPlatformError


class DummyAdapter(PlatformAdapter):
    name = "dummy"

    def matches(self, url: str) -> bool:
        return url.startswith("https://dummy.local/")


def test_resolve_known_platforms() -> None:
    assert resolve_platform("https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007").name == "bilibili"
    assert resolve_platform("https://youtu.be/abc123?t=30").name == "youtube"
    assert resolve_platform("https://www.xiaoyuzhoufm.com/episode/123?utm_source=foo").name == "xiaoyuzhou"


def test_normalize_urls() -> None:
    bilibili = resolve_platform("https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007&p=2")
    youtube = resolve_platform("https://youtu.be/abc123?t=30")
    xiaoyuzhou = resolve_platform("https://www.xiaoyuzhoufm.com/episode/123?utm_source=foo")

    assert bilibili.normalize_url("https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007&p=2") == "https://www.bilibili.com/video/BV1xx411c7mD/?p=2"
    assert youtube.normalize_url("https://youtu.be/abc123?t=30") == "https://www.youtube.com/watch?v=abc123"
    assert xiaoyuzhou.normalize_url("https://www.xiaoyuzhoufm.com/episode/123?utm_source=foo") == "https://www.xiaoyuzhoufm.com/episode/123"


def test_unsupported_platform_raises() -> None:
    with pytest.raises(UnsupportedPlatformError):
        resolve_platform("https://example.com/video/1")


def test_registry_can_be_extended() -> None:
    registry = PlatformRegistry()
    registry.register(DummyAdapter())
    assert registry.resolve_platform("https://dummy.local/test").name == "dummy"
