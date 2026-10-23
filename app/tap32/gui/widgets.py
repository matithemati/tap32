"""Wspólne widżety nowego interfejsu: przełącznik, kontrolka segmentowa, pomocnicze ramki."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from . import theme


def styled(widget: QWidget, **props: Any) -> QWidget:
    """Ustawia dynamiczne właściwości używane przez QSS (np. primary=True)."""
    for name, value in props.items():
        widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def frame(name: str) -> QFrame:
    f = QFrame()
    f.setObjectName(name)
    return f


def hline() -> QFrame:
    line = frame("hline")
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


def combo() -> QComboBox:
    """Lista rozwijana, której szerokość nie zależy od najdłuższej pozycji."""
    c = QComboBox()
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(8)
    return c


def button(
    text: str = "", icon_name: str | None = None, *, primary: bool = False, ghost: bool = False
) -> QPushButton:
    b = QPushButton(text)
    if icon_name:
        b.setIcon(theme.icon(icon_name, "on_primary" if primary else "text"))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary or ghost:
        styled(b, primary=primary, ghost=ghost)
    return b


class Switch(QCheckBox):
    """Przełącznik w stylu iOS (API QCheckBox: isChecked/setChecked/toggled)."""

    TRACK_W = 34
    TRACK_H = 20

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.text()) + 10 if self.text() else 0
        return QSize(self.TRACK_W + 4 + text_w, max(self.TRACK_H + 4, fm.height() + 4))

    def hitButton(self, pos: Any) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = (self.height() - self.TRACK_H) / 2
        track = QRectF(1, y, self.TRACK_W, self.TRACK_H)
        on = self.isChecked()
        track_color = theme.color("primary" if on else "switch_off")
        if not self.isEnabled():
            track_color.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(track, self.TRACK_H / 2, self.TRACK_H / 2)
        knob_x = track.right() - 18 if on else track.left() + 2
        p.setBrush(theme.color("on_primary") if on else Qt.GlobalColor.white)
        p.drawEllipse(QRectF(knob_x, y + 2, 16, 16))
        if self.hasFocus():
            pen = p.pen()
            pen.setColor(theme.color("accent"))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(
                track.adjusted(-2, -2, 2, 2), self.TRACK_H / 2 + 2, self.TRACK_H / 2 + 2
            )
        if self.text():
            p.setPen(theme.color("text" if self.isEnabled() else "faint"))
            p.drawText(
                QRectF(self.TRACK_W + 12, 0, self.width() - self.TRACK_W - 12, self.height()),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                self.text(),
            )


class Segmented(QFrame):
    """Kontrolka segmentowa: wzajemnie wykluczające się przyciski."""

    changed = Signal(object)

    def __init__(self, items: Sequence[tuple[Any, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("seg")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[Any, QPushButton] = {}
        for value, text in items:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            styled(b, seg=True)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self.group.addButton(b)
            self.buttons[value] = b
            layout.addWidget(b)

    def set_value(self, value: Any) -> None:
        b = self.buttons.get(value)
        if b is not None:
            b.setChecked(True)

    def value(self) -> Any:
        for v, b in self.buttons.items():
            if b.isChecked():
                return v
        return None

    def set_text(self, value: Any, text: str) -> None:
        if value in self.buttons:
            self.buttons[value].setText(text)
