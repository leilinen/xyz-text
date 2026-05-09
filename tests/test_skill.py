from __future__ import annotations

import json
import subprocess

from media_transcript_skill import run_skill


class FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_skill_returns_error_for_missing_url() -> None:
    result = run_skill({})
    assert result["ok"] is False
    assert "url is required" in result["error"]
    assert result["error_type"] == "ValidationError"


def test_skill_returns_success_payload(monkeypatch) -> None:
    payload = {"ok": True, "result": {"summary": "done"}}

    def fake_run(*args, **kwargs):
        return FakeCompleted(0, stdout=json.dumps(payload))

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_skill({"url": "https://youtu.be/abc"})
    assert result == payload


def test_skill_handles_invalid_json(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return FakeCompleted(0, stdout="not-json")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_skill({"url": "https://youtu.be/abc"})
    assert result["ok"] is False
    assert result["error"] == "media processor returned invalid JSON"
    assert result["error_type"] == "ProtocolError"


def test_skill_handles_empty_stdout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return FakeCompleted(0, stdout="   ", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_skill({"url": "https://youtu.be/abc"})
    assert result["ok"] is False
    assert result["error"] == "media processor returned empty stdout"
    assert result["error_type"] == "ProtocolError"


def test_skill_handles_non_zero_exit_with_json_payload(monkeypatch) -> None:
    payload = {"ok": False, "error": "boom", "error_type": "ExternalCommandError"}

    def fake_run(*args, **kwargs):
        return FakeCompleted(1, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_skill({"url": "https://youtu.be/abc"})
    assert result == payload


def test_skill_handles_non_zero_exit(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return FakeCompleted(1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_skill({"url": "https://youtu.be/abc"})
    assert result["ok"] is False
    assert result["error"] == "boom"
    assert result["error_type"] == "ProcessExecutionError"
