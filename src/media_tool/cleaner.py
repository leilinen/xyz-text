from __future__ import annotations

import re
from collections import OrderedDict

from .config import get_settings

_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[\.,]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[\.,]\d{3}$")
_VTT_HEADER_RE = re.compile(r"^(WEBVTT|Kind:|Language:)")
_TAG_RE = re.compile(r"<[^>]+>")
_CUE_SETTING_RE = re.compile(r"\b(?:align|position|size|line):\S+")


def clean_transcript_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    lines: list[str] = []
    seen = OrderedDict()
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        # Remove cue settings and tags first, before checking for timestamps
        line = _CUE_SETTING_RE.sub("", line).strip()
        line = _TAG_RE.sub("", line)
        if not line or line.isdigit() or _TIMESTAMP_RE.match(line) or _VTT_HEADER_RE.match(line):
            continue
        line = re.sub(r"\s+", " ", line).strip(" -")
        if not line:
            continue
        seen[line] = None
    lines = list(seen.keys())
    return "\n".join(lines)


_SENTENCE_END_RE = re.compile(r"[。！？!?]")


def needs_punctuation(text: str) -> bool:
    """Check whether text lacks sentence-ending punctuation."""
    sample = text[:2000]
    sentence_ends = len(_SENTENCE_END_RE.findall(sample))
    # If fewer than 1 sentence-ending mark per 200 chars, treat as unpunctuated
    return sentence_ends < len(sample) / 200


def split_paragraphs(text: str, paragraph_length: int | None = None) -> list[str]:
    """Split cleaned text into readable paragraphs at sentence boundaries."""
    settings = get_settings()
    target_len = paragraph_length or settings.cleaner_paragraph_length
    sentences = re.split(r"(?<=[。！？])", text.replace("\n", " "))
    sentences = [s.strip() for s in sentences if s.strip()]
    paragraphs: list[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
            continue
        if len(current) + len(sentence) <= target_len:
            current += sentence
        else:
            paragraphs.append(current)
            current = sentence
    if current:
        paragraphs.append(current)
    return paragraphs


def split_segments(text: str, segment_length: int | None = None, min_sentence_length: int | None = None) -> list[str]:
    settings = get_settings()
    max_len = segment_length or settings.cleaner_segment_length
    min_len = min_sentence_length or settings.cleaner_min_sentence_length
    sentences = [part.strip() for part in re.split(r"(?<=[。！？!?\.])\s+", text.replace("\n", " ")) if part.strip()]
    segments: list[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
            continue
        # Merge if current is too short, or if adding sentence doesn't exceed max_len by more than 1 char
        if len(current) < min_len or len(current) + len(sentence) + 1 <= max_len + 1:
            current = f"{current} {sentence}".strip()
        else:
            segments.append(current)
            current = sentence
    if current:
        segments.append(current)
    return segments
