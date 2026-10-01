"""Compatibility wrapper for :mod:`media_tool.integrations.llm`."""

from .integrations.llm import *  # noqa: F401,F403
from .integrations import llm as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
