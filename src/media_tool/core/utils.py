from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MediaToolError(RuntimeError):
    pass


class UnsupportedPlatformError(MediaToolError):
    pass


class ExternalCommandError(MediaToolError):
    pass


class ASRError(MediaToolError):
    pass


class FeishuAPIError(MediaToolError):
    pass


class SummarizationError(MediaToolError):
    pass


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=False)
            elif path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning("failed to clean up %s: %s", path, exc)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def safe_json_loads(value: str) -> dict[str, Any]:
    """Robust JSON parser for LLM output. Handles markdown blocks, <think/> tags,
    surrounding text, trailing commas, and other common small-model quirks."""
    stripped = value.strip()

    # Strip markdown code blocks if present
    if stripped.startswith("```json"):
        lines = stripped.split("\n")
        if lines[0].startswith("```json"):
            lines = lines[1:]
        if lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    elif stripped.startswith("```"):
        lines = stripped.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    # Strip <think/> tags (common with thinking models like qwen3.5)
    stripped = re.sub(r"<think.*?>.*?</think\s*>", "", stripped, flags=re.DOTALL)
    stripped = re.sub(r"<think.*/>", "", stripped)
    stripped = stripped.strip()

    def _try_parse(text: str) -> dict[str, Any] | None:
        """Try to parse text as JSON, with common fixes."""
        # Direct parse
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError:
            pass
        # Fix trailing commas
        fixed = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            data = json.loads(fixed)
            if isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError:
            pass
        return None

    # Attempt 1: Parse the whole thing
    result = _try_parse(stripped)
    if result is not None:
        return result

    # Attempt 2: Extract { ... } using balanced brace matching
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace:last_brace + 1]
        result = _try_parse(candidate)
        if result is not None:
            return result

    # Attempt 3: Regex extraction (greedy match)
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        result = _try_parse(match.group())
        if result is not None:
            return result

    # Last resort: if output looks like plain text/markdown, wrap it as a summary
    if text and not text.strip().startswith("{"):
        summary_text = text.strip()
        title = ""
        for line in summary_text.split("\n"):
            line_s = line.strip().lstrip("#").strip()
            if line_s and len(line_s) < 50:
                title = line_s
                break
        result = {
            "title": title or "媒体内容总结",
            "summary": summary_text[:2000],
            "one_line_summary": title or "",
            "topics": [],
            "key_points": [],
            "quotes": [],
            "entities": [],
        }
        logger.warning("LLM output was not JSON; parsed as plain-text summary (%d chars)", len(summary_text))
        return result

    raise SummarizationError(
        f"model output is not valid JSON (first 200 chars: {stripped[:200]})"
    )
