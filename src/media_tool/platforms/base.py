from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    args: list[str] = field(default_factory=list)


class PlatformAdapter(ABC):
    name: str

    @abstractmethod
    def matches(self, url: str) -> bool:
        raise NotImplementedError

    def normalize_url(self, url: str) -> str:
        return url.strip()

    def subtitle_languages(self) -> list[str]:
        return ["zh-Hans", "zh-CN", "zh", "en"]

    def build_subtitle_request(self, url: str, output_template: str) -> DownloadRequest:
        return DownloadRequest(
            url=self.normalize_url(url),
            args=[
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                ",".join(self.subtitle_languages()),
                "--convert-subs",
                "vtt",
                "-o",
                output_template,
            ],
        )

    def build_audio_request(self, url: str, output_template: str) -> DownloadRequest:
        return DownloadRequest(
            url=self.normalize_url(url),
            args=[
                "-x",
                "--audio-format",
                "mp3",
                "-o",
                output_template,
            ],
        )
