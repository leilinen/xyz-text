"""Compatibility wrapper for :mod:`media_tool.enrichment.comments`."""

from .enrichment.comments import *  # noqa: F401,F403
from .enrichment import comments as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
