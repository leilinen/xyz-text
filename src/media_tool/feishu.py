"""Compatibility wrapper for :mod:`media_tool.integrations.feishu`."""

from .integrations.feishu import *  # noqa: F401,F403
from .integrations import feishu as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
