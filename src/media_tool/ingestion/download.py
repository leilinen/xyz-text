from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..core.utils import ExternalCommandError
from ..core.yt_dlp import build_yt_dlp_auth_args

logger = logging.getLogger(__name__)

_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts"}


def download_video_files(request_args: list[str], url: str) -> None:
    """Execute yt-dlp to download video file(s)."""
    command = ["yt-dlp", *build_yt_dlp_auth_args(), *request_args, url]
    logger.info("downloading video: %s", " ".join(command))
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info("yt-dlp stdout: %s", result.stdout[:500] if result.stdout else "(empty)")
    except subprocess.CalledProcessError as exc:
        logger.error(
            "yt-dlp video download failed (rc=%d): stderr=%s",
            exc.returncode,
            exc.stderr[:500] if exc.stderr else "(empty)",
        )
        raise ExternalCommandError(
            exc.stderr.strip() or exc.stdout.strip() or "yt-dlp video download failed"
        ) from exc


def detect_playlist(url: str) -> bool:
    """Use yt-dlp to detect if URL points to a playlist (multiple videos)."""
    try:
        result = subprocess.run(
            ["yt-dlp", *build_yt_dlp_auth_args(), "--flat-playlist", "--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return False
        lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
        return len(lines) > 1
    except Exception:
        return False


def list_downloaded_files(output_dir: Path) -> list[Path]:
    """Return video files in output_dir, sorted by name."""
    files = [f for f in output_dir.iterdir() if f.is_file() and f.suffix.lower() in _VIDEO_EXTENSIONS]
    return sorted(files, key=lambda p: p.name.lower())
