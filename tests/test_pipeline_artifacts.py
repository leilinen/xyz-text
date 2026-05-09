from __future__ import annotations

from pathlib import Path

import pytest

from src.media_tool.asr import choose_audio_file
from src.media_tool.pipeline import process_media
from src.media_tool.subtitles import choose_subtitle_file
from src.media_tool.utils import ExternalCommandError


class DummyAdapter:
    name = "dummy"

    def normalize_url(self, url: str) -> str:
        return url


def test_choose_subtitle_file_prefers_manual_chinese(tmp_path: Path) -> None:
    auto_en = tmp_path / "video.en.auto.vtt"
    manual_zh = tmp_path / "video.zh-Hans.vtt"
    manual_en = tmp_path / "video.en.vtt"
    for path in (auto_en, manual_zh, manual_en):
        path.write_text("subtitle", encoding="utf-8")

    assert choose_subtitle_file([auto_en, manual_en, manual_zh]) == manual_zh


def test_choose_audio_file_prefers_supported_priority(tmp_path: Path) -> None:
    webm = tmp_path / "audio.webm"
    m4a = tmp_path / "audio.m4a"
    mp3 = tmp_path / "audio.mp3"
    for path in (webm, m4a, mp3):
        path.write_text("audio", encoding="utf-8")

    assert choose_audio_file([webm, m4a, mp3]) == mp3


def test_process_media_cleans_run_dir_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"work_dir": "%s", "temp_dir": "%s"}' % (tmp_path / "work", tmp_path / "work" / "tmp"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fake_resolve_platform(url: str) -> DummyAdapter:
        return DummyAdapter()

    def fake_extract_subtitles(adapter: object, url: str, work_dir: Path):
        (work_dir / "artifact.txt").write_text("data", encoding="utf-8")
        return None

    def fake_extract_audio_and_transcribe(adapter: object, url: str, work_dir: Path, model=None):
        raise ExternalCommandError("boom")

    monkeypatch.setattr("src.media_tool.pipeline.resolve_platform", fake_resolve_platform)
    monkeypatch.setattr("src.media_tool.pipeline.extract_subtitles", fake_extract_subtitles)
    monkeypatch.setattr("src.media_tool.pipeline.extract_audio_and_transcribe", fake_extract_audio_and_transcribe)

    with pytest.raises(ExternalCommandError):
        process_media("https://example.com/test")

    temp_root = tmp_path / "work" / "tmp" / "dummy"
    assert not any(temp_root.iterdir()) if temp_root.exists() else True
