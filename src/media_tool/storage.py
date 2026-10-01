"""Compatibility wrapper for :mod:`media_tool.outputs.storage`."""

from .outputs.storage import *  # noqa: F401,F403
from .outputs import storage as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
