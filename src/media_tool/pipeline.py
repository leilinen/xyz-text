"""Compatibility wrapper for :mod:`media_tool.orchestration.pipeline`."""

from .orchestration.pipeline import *  # noqa: F401,F403
from .orchestration import pipeline as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
