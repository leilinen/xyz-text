"""Compatibility wrapper for :mod:`media_tool.ingestion.asr`."""

from .ingestion.asr import *  # noqa: F401,F403
from .ingestion import asr as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
