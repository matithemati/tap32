"""Strona „Dziennik”: ostatnie zdarzenia i błędy."""

from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from ..core.logbuffer import LogEntry
from . import theme
from .i18n import tr
from .widgets import Segmented, button, frame, label

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
MAX_LINES = 2000

# kolory etykiet poziomów: (tło, tekst) – jasny / ciemny motyw
LEVEL_COLORS = {
    "DEBUG": (("#F0F0F2", "#3A3A40"), ("#26262B", "#B4B4BC")),
    "INFO": (("#EAF1FE", "#1D4ED8"), ("#16213A", "#A9C2FF")),
    "WARNING": (("#FFF3DC", "#8A5200"), ("#33270F", "#F5C46B")),
    "ERROR": (("#FDECEC", "#A3241A"), ("#3A1614", "#F97066")),
    "CRITICAL": (("#FDECEC", "#A3241A"), ("#3A1614", "#F97066")),
}


class LogView(QWidget):
    errorCountChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text = QPlainTextEdit()
        self.text.setObjectName("log")
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(MAX_LINES)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.level = Segmented(
            [(0, tr("Wszystko")), (30, tr("Ostrzeżenia i błędy")), (40, tr("Tylko błędy"))]
        )
        self.level.set_value(0)
        self.level.changed.connect(lambda _: self._reload())
        clear = button(tr("Wyczyść"), "trash")
        clear.clicked.connect(self._clear)

        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(label(tr("Dziennik"), "h1"))
        titles.addWidget(label(tr("Ostatnie zdarzenia i błędy."), "hint"))
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addLayout(titles, 1)
        top.addWidget(label(tr("Pokaż"), "lbl"), 0, Qt.AlignmentFlag.AlignBottom)
        top.addWidget(self.level, 0, Qt.AlignmentFlag.AlignBottom)
        top.addWidget(clear, 0, Qt.AlignmentFlag.AlignBottom)

        card = frame("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(1, 1, 1, 1)
        cl.addWidget(self.text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(top)
        layout.addWidget(card, 1)
        self._entries: list[LogEntry] = []

    def _threshold(self) -> int:
        return int(self.level.value() or 0)

    def error_count(self) -> int:
        return sum(1 for e in self._entries if LEVELS.get(e.level, 20) >= 40)

    def add(self, entry: LogEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > MAX_LINES:
            self._entries = self._entries[-MAX_LINES:]
        if LEVELS.get(entry.level, 20) >= self._threshold():
            self._append(entry)
        if LEVELS.get(entry.level, 20) >= 40:
            self.errorCountChanged.emit(self.error_count())

    def entries(self) -> list[LogEntry]:
        return list(self._entries)

    def _append(self, entry: LogEntry) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime(entry.time))
        light, dark = LEVEL_COLORS.get(entry.level, LEVEL_COLORS["INFO"])
        bg, fg = dark if theme.is_dark() else light
        muted = theme.tokens()["muted"]
        text = theme.tokens()["text"]
        line = (
            f'<span style="color:{muted}">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="background:{bg}; color:{fg}; font-weight:600">'
            f"&nbsp;{entry.level:<8}&nbsp;</span>"
            f'&nbsp;&nbsp;<span style="color:{text}">{html.escape(entry.message)}</span>'
        ).replace("  ", "&nbsp;&nbsp;")
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.appendHtml(line)

    def _reload(self) -> None:
        self.text.clear()
        for entry in self._entries:
            if LEVELS.get(entry.level, 20) >= self._threshold():
                self._append(entry)

    def _clear(self) -> None:
        self._entries.clear()
        self.text.clear()
        self.errorCountChanged.emit(0)
