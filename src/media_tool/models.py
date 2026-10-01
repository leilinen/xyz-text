"""Compatibility wrapper for :mod:`media_tool.core.models`."""

from .core.models import *  # noqa: F401,F403
from .core import models as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
