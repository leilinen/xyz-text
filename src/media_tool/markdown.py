"""Compatibility wrapper for :mod:`media_tool.outputs.markdown`."""

from .outputs.markdown import *  # noqa: F401,F403
from .outputs import markdown as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
