"""Compatibility wrapper for :mod:`media_tool.core.config`."""

from .core.config import *  # noqa: F401,F403
from .core import config as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
