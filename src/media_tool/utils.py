"""Compatibility wrapper for :mod:`media_tool.core.utils`."""

from .core.utils import *  # noqa: F401,F403
from .core import utils as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
