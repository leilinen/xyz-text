from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .models import SubtitleResult
from .utils import ExternalCommandError, read_text_file

logger = logging.getLogger(__name__)

_PREFERRED_SUBTITLE_LANG_PREFIXES = ("zh", "cmn", "yue")


def fetch_video_metadata(url: str) -> dict[str, str | None]:
    """Fetch video title and description via yt-dlp --dump-json."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("yt-dlp metadata fetch failed: %s", result.stderr[:200])
            return {}
        info = json.loads(result.stdout)
        return {
            "title": info.get("title"),
            "description": info.get("description"),
        }
    except Exception as exc:
        logger.warning("failed to fetch video metadata: %s", exc)
        return {}


def download_subtitles(request_args: list[str], url: str) -> None:
    command = ["yt-dlp", *request_args, url]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise ExternalCommandError(exc.stderr.strip() or exc.stdout.strip() or "yt-dlp subtitle download failed") from exc


def parse_subtitle_file(path: Path) -> SubtitleResult:
    suffix = path.suffix.lower()
    if suffix not in {".vtt", ".srt"}:
        raise ExternalCommandError(f"unsupported subtitle file format: {path}")
    text = read_text_file(path)
    return SubtitleResult(
        text=text,
        source_path=path,
        language=_extract_subtitle_language(path),
        is_auto_generated=_is_auto_generated_subtitle(path),
    )


def _extract_subtitle_language(path: Path) -> str | None:
    parts = path.stem.split(".")
    if not parts:
        return None
    candidates = [part.lower() for part in parts[1:]]
    for candidate in reversed(candidates):
        if candidate and candidate != "auto":
            return candidate
    return None


def _is_auto_generated_subtitle(path: Path) -> bool:
    parts = {part.lower() for part in path.stem.split(".")}
    return "auto" in parts or "automatic" in parts


def _subtitle_sort_key(path: Path) -> tuple[int, int, int, str]:
    language = _extract_subtitle_language(path) or ""
    is_auto = _is_auto_generated_subtitle(path)
    normalized_language = language.lower()
    manual_rank = 1 if is_auto else 0
    chinese_rank = 0 if normalized_language.startswith(_PREFERRED_SUBTITLE_LANG_PREFIXES) else 1
    extension_rank = 0 if path.suffix.lower() == ".srt" else 1
    return (manual_rank, chinese_rank, extension_rank, path.name.lower())


def choose_subtitle_file(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return sorted(paths, key=_subtitle_sort_key)[0]


def extract_subtitles(adapter: object, url: str, work_dir: Path) -> SubtitleResult | None:
    output_template = str(work_dir / "%(title)s.%(ext)s")
    request = adapter.build_subtitle_request(url, output_template)
    download_subtitles(request.args, request.url)
    subtitle_files = list(work_dir.glob("*.vtt")) + list(work_dir.glob("*.srt"))
    preferred = choose_subtitle_file(subtitle_files)
    if preferred is None:
        return None
    return parse_subtitle_file(preferred)
