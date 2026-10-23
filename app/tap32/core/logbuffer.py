"""Bufor ostatnich wpisów dziennika (zakładka „Dziennik” w GUI)."""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class LogEntry:
    time: float
    level: str
    name: str
    message: str


class LogBuffer(logging.Handler):
    def __init__(self, capacity: int = 1000) -> None:
        super().__init__(level=logging.INFO)
        self.entries: deque[LogEntry] = deque(maxlen=capacity)
        self._listeners: list[Callable[[LogEntry], None]] = []
        self._lock_entries = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(record.created, record.levelname, record.name, record.getMessage())
        except Exception:
            return
        with self._lock_entries:
            self.entries.append(entry)
        for listener in list(self._listeners):
            try:
                listener(entry)
            except Exception:
                pass

    def add_listener(self, listener: Callable[[LogEntry], None]) -> None:
        self._listeners.append(listener)

    def snapshot(self) -> list[LogEntry]:
        with self._lock_entries:
            return list(self.entries)


def setup_logging(log_file: str | None = None, verbose: bool = False) -> LogBuffer:
    buffer = LogBuffer()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root.addHandler(buffer)
    if log_file:
        from logging.handlers import RotatingFileHandler

        handler = RotatingFileHandler(log_file, maxBytes=512_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(fmt)
        root.addHandler(handler)
    if verbose:
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)
    return buffer
