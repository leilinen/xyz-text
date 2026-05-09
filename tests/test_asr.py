from __future__ import annotations

from pathlib import Path

import pytest

from src.media_tool.asr import transcribe_audio
from src.media_tool.config import get_settings
from src.media_tool.models import TranscriptResult


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.mp3"
    path.write_bytes(b"audio")
    return path


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / "config.json"
    monkeypatch.chdir(tmp_path)
    return config_path


def test_get_settings_defaults(config_file: Path) -> None:
    config_file.write_text("{}", encoding="utf-8")
    settings = get_settings(config_file)
    assert settings.sensevoice_device == "cpu"
    assert settings.sensevoice_language == "auto"


def test_transcribe_audio_calls_sensevoice(monkeypatch: pytest.MonkeyPatch, config_file: Path, audio_file: Path) -> None:
    config_file.write_text("{}", encoding="utf-8")
    test_settings = get_settings(config_file)
    monkeypatch.setattr("src.media_tool.asr.get_settings", lambda: test_settings)

    fake_result = TranscriptResult(text="hello world", segments=[], audio_path=audio_file)

    def fake_sensevoice(path: Path) -> TranscriptResult:
        return fake_result

    monkeypatch.setattr("src.media_tool.asr.transcribe_audio_with_sensevoice", fake_sensevoice)
    result = transcribe_audio(audio_file)
    assert result.text == "hello world"
