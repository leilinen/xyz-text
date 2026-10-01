from __future__ import annotations

from pathlib import Path

from .config import Settings, get_settings

# Recent YouTube requires solving JS challenges with an external solver (EJS);
# without it yt-dlp fails with "The page needs to be reloaded" even when
# cookies are valid. The solver script is fetched once from GitHub and cached.
_EJS_REMOTE_COMPONENTS = ["--remote-components", "ejs:github"]


def build_yt_dlp_common_args(settings: Settings | None = None) -> list[str]:
    """Arguments shared by every yt-dlp invocation: challenge solver and auth."""
    active = settings or get_settings()
    auth_args: list[str] = []
    if active.yt_dlp_cookies_file:
        cookies_file = active.yt_dlp_cookies_file
        if not cookies_file.is_absolute():
            cookies_file = Path(__file__).resolve().parents[3] / cookies_file
        auth_args = ["--cookies", str(cookies_file)]
    elif active.yt_dlp_cookies_from_browser:
        auth_args = ["--cookies-from-browser", active.yt_dlp_cookies_from_browser]
    return [*_EJS_REMOTE_COMPONENTS, *auth_args]


def build_yt_dlp_auth_args(settings: Settings | None = None) -> list[str]:
    """Compatibility alias for :func:`build_yt_dlp_common_args`."""
    return build_yt_dlp_common_args(settings)
