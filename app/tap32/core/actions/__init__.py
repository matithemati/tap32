"""Akcje Tap32: rejestr typów i wykonawca."""

from . import builtin as _builtin  # noqa: F401 - rejestracja typów
from .base import (
    ACTION_TYPES,
    Action,
    ActionBase,
    ActionContext,
    ActionHost,
    UnknownAction,
    make_action,
    parse_action,
    register_action,
)
from .builtin import MacroStep, format_hotkey, parse_hotkey
from .executor import ActionExecutor

__all__ = [
    "ACTION_TYPES",
    "Action",
    "ActionBase",
    "ActionContext",
    "ActionExecutor",
    "ActionHost",
    "MacroStep",
    "UnknownAction",
    "format_hotkey",
    "make_action",
    "parse_action",
    "parse_hotkey",
    "register_action",
]
