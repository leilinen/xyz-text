from __future__ import annotations

from pathlib import Path

from .config import Settings, get_settings


def build_yt_dlp_auth_args(settings: Settings | None = None) -> list[str]:
    active = settings or get_settings()
    if active.yt_dlp_cookies_file:
        cookies_file = active.yt_dlp_cookies_file
        if not cookies_file.is_absolute():
            cookies_file = Path(__file__).resolve().parents[3] / cookies_file
        return ["--cookies", str(cookies_file)]
    if active.yt_dlp_cookies_from_browser:
        return ["--cookies-from-browser", active.yt_dlp_cookies_from_browser]
    return []
