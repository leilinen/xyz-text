"""Compatibility wrapper for :mod:`media_tool.text.summarizer`."""

from .text.summarizer import *  # noqa: F401,F403
from .text import summarizer as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
