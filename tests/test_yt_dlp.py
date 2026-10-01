from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from media_tool.core.config import get_settings
from media_tool.core.yt_dlp import build_yt_dlp_auth_args, build_yt_dlp_common_args


@pytest.fixture()
def settings(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({}))
    return get_settings(config)


def test_common_args_include_ejs_challenge_solver(settings):
    args = build_yt_dlp_common_args(settings)
    assert "--remote-components" in args
    assert args[args.index("--remote-components") + 1] == "ejs:github"


def test_cookies_from_browser(settings):
    active = replace(settings, yt_dlp_cookies_from_browser="edge:Default")
    args = build_yt_dlp_common_args(active)
    assert "--cookies-from-browser" in args
    assert args[args.index("--cookies-from-browser") + 1] == "edge:Default"


def test_cookies_file_preferred_over_browser(settings):
    active = replace(
        settings,
        yt_dlp_cookies_from_browser="edge",
        yt_dlp_cookies_file=Path("/tmp/cookies.txt"),
    )
    args = build_yt_dlp_common_args(active)
    assert "--cookies" in args
    assert "--cookies-from-browser" not in args


def test_relative_cookies_file_resolved_from_project_root(settings):
    active = replace(settings, yt_dlp_cookies_file=Path("cookies.txt"))
    args = build_yt_dlp_common_args(active)
    resolved = args[args.index("--cookies") + 1]
    assert Path(resolved).is_absolute()


def test_auth_args_alias_matches_common_args(settings):
    active = replace(settings, yt_dlp_cookies_from_browser="edge:Default")
    assert build_yt_dlp_auth_args(active) == build_yt_dlp_common_args(active)
