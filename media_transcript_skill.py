from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


_PROCESSOR_PATH = Path(__file__).resolve().with_name("media_processor.py")


def _build_processor_error(message: str, *, error_type: str = "SkillExecutionError", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": message,
        "error_type": error_type,
    }
    payload.update(extra)
    return payload


def run_skill(payload: dict[str, Any]) -> dict[str, Any]:
    url = payload.get("url")
    if not url:
        return _build_processor_error("url is required", error_type="ValidationError")

    command = [sys.executable, str(_PROCESSOR_PATH), url]
    if payload.get("no_feishu"):
        command.append("--no-feishu")
    if payload.get("no_cleanup"):
        command.append("--no-cleanup")

    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except Exception as exc:
        return _build_processor_error(f"failed to execute media processor: {exc}")

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    if completed.returncode != 0:
        if stdout:
            try:
                result = json.loads(stdout)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(result, dict):
                    return result
        return _build_processor_error(
            stderr or stdout or "media processor failed with no output",
            error_type="ProcessExecutionError",
        )

    if not stdout:
        return _build_processor_error("media processor returned empty stdout", error_type="ProtocolError")

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return _build_processor_error(
            "media processor returned invalid JSON",
            error_type="ProtocolError",
            raw_output=stdout,
            stderr=stderr or None,
        )

    if not isinstance(result, dict):
        return _build_processor_error(
            "media processor returned unexpected payload",
            error_type="ProtocolError",
            raw_output=stdout,
        )
    return result
