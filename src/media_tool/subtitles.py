"""Compatibility wrapper for :mod:`media_tool.ingestion.subtitles`."""

from .ingestion.subtitles import *  # noqa: F401,F403
from .ingestion import subtitles as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
