"""Aggregated effect name constants grouped by theme."""

from .base import *  # noqa: F401,F403
from .plugin import *  # noqa: F401,F403
from .hero import *  # noqa: F401,F403

__all__ = [name for name in globals() if name.startswith("EFFECT_NAME_")]
