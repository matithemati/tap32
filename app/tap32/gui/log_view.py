"""Zakładka „Dziennik”: ostatnie zdarzenia i błędy."""

from __future__ import annotations

import time

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.logbuffer import LogEntry

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
MAX_LINES = 2000


class LogView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(MAX_LINES)
        self.text.setStyleSheet("font-family: Consolas, monospace;")
        self.level = QComboBox()
        self.level.addItem("Wszystko", 0)
        self.level.addItem("Ostrzeżenia i błędy", 30)
        self.level.addItem("Tylko błędy", 40)
        self.level.currentIndexChanged.connect(self._reload)
        clear = QPushButton("Wyczyść")
        clear.clicked.connect(self._clear)
        top = QHBoxLayout()
        top.addWidget(QLabel("Pokaż:"))
        top.addWidget(self.level)
        top.addStretch(1)
        top.addWidget(clear)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.text)
        self._entries: list[LogEntry] = []

    def add(self, entry: LogEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > MAX_LINES:
            self._entries = self._entries[-MAX_LINES:]
        if LEVELS.get(entry.level, 20) >= self.level.currentData():
            self._append(entry)

    def _append(self, entry: LogEntry) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime(entry.time))
        color = {"WARNING": "#f39c12", "ERROR": "#e74c3c", "CRITICAL": "#e74c3c"}.get(entry.level)
        line = f"{stamp}  {entry.level:<7} {entry.message}"
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        if color:
            escaped = line.replace("&", "&amp;").replace("<", "&lt;")
            self.text.appendHtml(f'<span style="color:{color}">{escaped}</span>')
        else:
            self.text.appendPlainText(line)

    def _reload(self) -> None:
        self.text.clear()
        for entry in self._entries:
            if LEVELS.get(entry.level, 20) >= self.level.currentData():
                self._append(entry)

    def _clear(self) -> None:
        self._entries.clear()
        self.text.clear()
