from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaSource:
    url: str
    normalized_url: str
    platform: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubtitleResult:
    text: str
    source_path: Path | None
    language: str | None
    is_auto_generated: bool


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    audio_path: Path | None = None


@dataclass(frozen=True)
class Entity:
    name: str
    type: str  # "person" | "organization" | "book"
    context: str = ""


ENTITY_TYPE_LABELS = {
    "person": "人物",
    "organization": "组织",
    "book": "书籍",
}


@dataclass(frozen=True)
class SummaryResult:
    title: str
    summary: str
    topics: list[str]
    key_points: list[str]
    quotes: list[str]
    one_line_summary: str = ""
    entities: list[Entity] = field(default_factory=list)
    raw_response: str | None = None


@dataclass(frozen=True)
class Comment:
    author: str
    text: str
    like_count: int
    timestamp: int
    is_pinned: bool = False
    is_creator_favorited: bool = False


@dataclass(frozen=True)
class HotCommentsResult:
    comments: list[Comment]
    total_count: int


@dataclass(frozen=True)
class ShownoteContent:
    text: str
    images: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeishuDocResult:
    doc_token: str
    url: str


@dataclass(frozen=True)
class ProcessResult:
    source: MediaSource
    transcript_source: str
    transcript: str
    segments: list[str]
    summary: SummaryResult | None
    feishu: FeishuDocResult | None
    comments: HotCommentsResult | None = None
    shownote: ShownoteContent | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
