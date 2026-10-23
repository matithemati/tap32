"""Kod zależny od systemu operacyjnego."""

from __future__ import annotations

import sys

from .base import NullPlatform, PlatformBackend, PlatformError

__all__ = ["NullPlatform", "PlatformBackend", "PlatformError", "create_platform"]


def create_platform() -> PlatformBackend:
    """Zwraca implementację dla bieżącego systemu."""
    if sys.platform == "win32":
        from .windows import WindowsPlatform

        return WindowsPlatform()
    return NullPlatform()
