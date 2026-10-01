"""Compatibility wrapper for :mod:`media_tool.enrichment.shownotes`."""

from .enrichment.shownotes import *  # noqa: F401,F403
from .enrichment import shownotes as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
