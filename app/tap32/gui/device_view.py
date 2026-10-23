"""Wizualny Tap32: ekran i pokrętło nad siatką 3×3. Podświetla fizyczne naciśnięcia na żywo."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ..core.config import Profile
from ..core.protocol import ENCODER_KEY
from .oled import OledView

SELECT_COLOR = QColor("#4fc3f7")
PRESS_COLOR = QColor("#ffd54f")


class KeyTile(QWidget):
    clicked = Signal(int)

    def __init__(self, key: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.label = ""
        self.color = QColor("#3c4a5c")
        self.gestures: list[str] = []
        self.selected = False
        self.pressed_flash = 0.0
        self.setMinimumSize(92, 82)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Klawisz K{key}")

    def set_binding(self, label: str, color: str, gestures: list[str]) -> None:
        self.label = label
        self.color = QColor(color) if QColor(color).isValid() else QColor("#3c4a5c")
        self.gestures = gestures
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        # „cap” klawisza
        base = self.color
        if self.pressed_flash > 0:
            base = base.lighter(100 + int(80 * self.pressed_flash))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base.darker(160))
        p.drawRoundedRect(rect, 10, 10)
        p.setBrush(base)
        p.drawRoundedRect(rect.adjusted(5, 3, -5, -9), 8, 8)
        if self.selected or self.pressed_flash > 0:
            pen = QPen(PRESS_COLOR if self.pressed_flash > 0 else SELECT_COLOR, 3)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, 10, 10)
        # numer
        p.setPen(QColor(255, 255, 255, 140))
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, small.pointSizeF() * 0.8))
        p.setFont(small)
        p.drawText(
            rect.adjusted(10, 6, -8, -8),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            f"K{self.key}",
        )
        # etykieta
        label_font = QFont(self.font())
        label_font.setBold(True)
        label_font.setPointSizeF(label_font.pointSizeF() * 1.15)
        p.setFont(label_font)
        p.setPen(QColor("#ffffff"))
        p.drawText(rect.adjusted(6, 0, -6, -10), Qt.AlignmentFlag.AlignCenter, self.label or "—")
        # znaczniki gestów
        badges = {"tap": "T", "hold": "H", "double_tap": "2×"}
        x = rect.right() - 8
        p.setFont(small)
        for g in reversed(["tap", "hold", "double_tap"]):
            if g not in self.gestures:
                continue
            text = badges[g]
            w = 14 + 5 * (len(text) - 1)
            badge = QRectF(x - w, rect.bottom() - 24, w, 13)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 110))
            p.drawRoundedRect(badge, 4, 4)
            p.setPen(QColor("#e0f7fa"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)
            x -= w + 3


class KnobWidget(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.angle = 0.0
        self.pressed = False
        self.selected = False
        self.flash = 0.0
        self.setFixedSize(108, 108)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Pokrętło (obrót, przycisk = klawisz 10)")

    def rotate(self, steps: int) -> None:
        self.angle = (self.angle + steps * 18) % 360
        self.flash = 1.0
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = min(self.width(), self.height()) / 2 - 6
        if self.selected or self.pressed or self.flash > 0:
            color = PRESS_COLOR if (self.pressed or self.flash > 0) else SELECT_COLOR
            p.setPen(QPen(color, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, r + 3, r + 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#5f6b7a").darker(130 if self.pressed else 100))
        p.drawEllipse(c, r, r)
        p.setBrush(QColor("#8996a5"))
        p.drawEllipse(c, r * 0.78, r * 0.78)
        # rowki
        p.setPen(QPen(QColor(0, 0, 0, 60), 1.5))
        for i in range(24):
            a = math.radians(i * 15 + self.angle)
            p.drawLine(
                QPointF(c.x() + math.sin(a) * r * 0.8, c.y() - math.cos(a) * r * 0.8),
                QPointF(c.x() + math.sin(a) * r * 0.97, c.y() - math.cos(a) * r * 0.97),
            )
        a = math.radians(self.angle)
        pointer = QPen(QColor("#ffffff"), 4)
        pointer.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pointer)
        p.drawLine(
            QPointF(c.x() + math.sin(a) * r * 0.25, c.y() - math.cos(a) * r * 0.25),
            QPointF(c.x() + math.sin(a) * r * 0.65, c.y() - math.cos(a) * r * 0.65),
        )


class DeviceView(QWidget):
    keySelected = Signal(int)  # 1..9
    encoderSelected = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.oled = OledView(scale=3)
        self.knob = KnobWidget()
        self.knob.clicked.connect(self._select_encoder)

        top = QHBoxLayout()
        top.addWidget(self.oled, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        top.addWidget(self.knob, 0, Qt.AlignmentFlag.AlignVCenter)

        grid = QGridLayout()
        grid.setSpacing(6)
        self.tiles: dict[int, KeyTile] = {}
        for k in range(1, 10):
            tile = KeyTile(k)
            tile.clicked.connect(self._select_key)
            self.tiles[k] = tile
            grid.addWidget(tile, (k - 1) // 3, (k - 1) % 3)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addSpacing(8)
        layout.addLayout(grid, 1)
        self.setStyleSheet("DeviceView { background: transparent; }")

        self._fade = QTimer(self)
        self._fade.setInterval(30)
        self._fade.timeout.connect(self._fade_step)
        self._selected: int | None = None

    # ------------------------------------------------------------------ dane

    def set_profile(self, profile: Profile) -> None:
        for k, tile in self.tiles.items():
            binding = profile.keys[k]
            gestures = [g for g in ("tap", "hold", "double_tap") if binding.action_for(g)]
            tile.set_binding(binding.label, binding.color, gestures)
        self.knob.setToolTip(f"Pokrętło – przycisk: {profile.keys[ENCODER_KEY].label or '—'}")

    def select(self, key: int | None) -> None:
        """key 1..9, ENCODER_KEY (pokrętło) albo None."""
        self._selected = key
        for k, tile in self.tiles.items():
            tile.selected = k == key
            tile.update()
        self.knob.selected = key == ENCODER_KEY
        self.knob.update()

    def _select_key(self, key: int) -> None:
        self.select(key)
        self.keySelected.emit(key)

    def _select_encoder(self) -> None:
        self.select(ENCODER_KEY)
        self.encoderSelected.emit()

    # ------------------------------------------------------------------ podświetlanie na żywo

    def highlight_key(self, key: int, down: bool) -> None:
        if key == ENCODER_KEY:
            self.knob.pressed = down
            self.knob.update()
            return
        tile = self.tiles.get(key)
        if tile is None:
            return
        tile.pressed_flash = 1.0 if down else max(tile.pressed_flash, 0.6)
        tile.update()
        if not down:
            self._fade.start()

    def highlight_rotation(self, steps: int) -> None:
        self.knob.rotate(steps)
        self._fade.start()

    def _fade_step(self) -> None:
        active = False
        for tile in self.tiles.values():
            if tile.pressed_flash > 0:
                tile.pressed_flash = max(0.0, tile.pressed_flash - 0.08)
                tile.update()
                active = active or tile.pressed_flash > 0
        if self.knob.flash > 0:
            self.knob.flash = max(0.0, self.knob.flash - 0.08)
            self.knob.update()
            active = active or self.knob.flash > 0
        if not active:
            self._fade.stop()
