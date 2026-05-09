from __future__ import annotations

from collections.abc import Iterable

from .base import PlatformAdapter
from .bilibili import BilibiliPlatformAdapter
from .xiaoyuzhou import XiaoyuzhouPlatformAdapter
from .youtube import YouTubePlatformAdapter
from ..utils import UnsupportedPlatformError


class PlatformRegistry:
    def __init__(self, adapters: Iterable[PlatformAdapter] | None = None) -> None:
        self._adapters: list[PlatformAdapter] = list(adapters or [])

    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters.append(adapter)

    def resolve_platform(self, url: str) -> PlatformAdapter:
        for adapter in self._adapters:
            if adapter.matches(url):
                return adapter
        raise UnsupportedPlatformError(f"unsupported media platform: {url}")

    @property
    def adapters(self) -> tuple[PlatformAdapter, ...]:
        return tuple(self._adapters)


def default_registry() -> PlatformRegistry:
    return PlatformRegistry(
        [
            BilibiliPlatformAdapter(),
            YouTubePlatformAdapter(),
            XiaoyuzhouPlatformAdapter(),
        ]
    )


def resolve_platform(url: str) -> PlatformAdapter:
    return default_registry().resolve_platform(url)
