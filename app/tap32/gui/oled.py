"""Podgląd ekranu OLED 128×32 – układ zgodny z firmware (display.cpp)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from ..core.simulator import Screen

WIDTH, HEIGHT = 128, 32
ON = QColor("#7fd8ff")
OFF = QColor("#05080b")


def _font(px: int, bold: bool = False) -> QFont:
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(px)
    font.setBold(bold)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    return font


class _Fonts:
    """Czcionki tworzone leniwie (QFont wymaga istniejącej QGuiApplication)."""

    def __init__(self) -> None:
        self.SMALL = _font(8)
        self.TEXT = _font(10)
        self.MEDIUM = _font(12, bold=True)
        self.LARGE = _font(16, bold=True)
        self.HUGE = _font(20, bold=True)


_fonts: _Fonts | None = None


def fonts() -> _Fonts:
    global _fonts
    if _fonts is None:
        _fonts = _Fonts()
    return _fonts


def _center(p: QPainter, text: str, cx: int, baseline: int) -> None:
    w = QFontMetrics(p.font()).horizontalAdvance(text)
    p.drawText(QPoint(cx - w // 2, baseline), text)


def _center_fit(p: QPainter, text: str, baseline: int, fonts: list[QFont]) -> None:
    for i, font in enumerate(fonts):
        p.setFont(font)
        if QFontMetrics(font).horizontalAdvance(text) <= WIDTH - 2 or i == len(fonts) - 1:
            _center(p, text, WIDTH // 2, baseline)
            return


def _marker(p: QPainter, online: bool, inverted: bool = False) -> None:
    color = OFF if inverted else ON
    p.setPen(color)
    p.setBrush(color if online else Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPoint(WIDTH - 4, 3), 2, 2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(ON)


def render(screen: Screen) -> QImage:
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
    image.fill(OFF)
    if screen.kind == "off":
        return image
    p = QPainter(image)
    p.setPen(ON)
    f = fonts()
    SMALL, TEXT, MEDIUM, LARGE, HUGE = f.SMALL, f.TEXT, f.MEDIUM, f.LARGE, f.HUGE
    kind = screen.kind
    if kind == "splash":
        p.setFont(HUGE)
        _center(p, "Tap32", WIDTH // 2, 20)
        p.setFont(SMALL)
        _center(p, "fw sym.", WIDTH // 2, 31)
    elif kind == "offline":
        p.setFont(MEDIUM)
        _center(p, "Offline", WIDTH // 2, 13)
        p.setFont(TEXT)
        _center(p, "Czekam na aplikację", WIDTH // 2, 28)
        _marker(p, False)
    elif kind == "idle":
        p.setFont(LARGE)
        _center(p, "Tap32", WIDTH // 2, 22)
        _marker(p, screen.online)
    elif kind == "profile":
        _center_fit(p, screen.title, 23, [LARGE, MEDIUM, TEXT, SMALL])
        _marker(p, screen.online)
    elif kind == "grid":
        p.fillRect(QRect(0, 0, WIDTH, 8), ON)
        p.setPen(OFF)
        p.setFont(SMALL)
        p.drawText(QPoint(2, 7), screen.title)
        _marker(p, screen.online, inverted=True)
        p.setPen(ON)
        for r in range(3):
            for c in range(3):
                label = screen.labels[r * 3 + c] if len(screen.labels) > r * 3 + c else ""
                _center(p, label, c * 43 + 21, 15 + r * 8)
        p.drawLine(42, 9, 42, 31)
        p.drawLine(85, 9, 85, 31)
    elif kind == "text":
        if not screen.line2:
            _center_fit(p, screen.line1, 23, [LARGE, MEDIUM, TEXT])
        else:
            _center_fit(p, screen.line1, 13, [MEDIUM, TEXT])
            _center_fit(p, screen.line2, 29, [TEXT, SMALL])
    elif kind == "bar":
        p.setFont(TEXT)
        p.drawText(QPoint(0, 10), screen.title)
        pct = f"{screen.value}%"
        p.drawText(QPoint(WIDTH - QFontMetrics(TEXT).horizontalAdvance(pct), 10), pct)
        p.drawRect(QRect(0, 16, WIDTH - 1, 13))
        fill = (WIDTH - 4) * screen.value // 100
        if fill > 0:
            p.fillRect(QRect(2, 18, fill, 10), ON)
    elif kind == "flash":
        _center_fit(p, screen.line1, 24, [HUGE, LARGE, MEDIUM, TEXT])
        if screen.key:
            p.setFont(SMALL)
            p.drawText(QPoint(0, 7), f"K{screen.key}")
    elif kind == "test":
        for r in range(3):
            for c in range(3):
                rect = QRect(1 + c * 11, 1 + r * 10, 8, 8)
                pressed = screen.test_keys[r * 3 + c] if screen.test_keys else False
                if pressed:
                    p.fillRect(rect, ON)
                else:
                    p.drawRect(rect)
        p.setBrush(ON if screen.test_keys and screen.test_keys[9] else Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPoint(43, 15), 6, 6)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setFont(SMALL)
        p.drawText(QPoint(56, 7), "TEST")
        p.drawText(QPoint(56, 28), f"zab {screen.test_steps}")
    p.end()
    if screen.flip:
        image = image.mirrored(True, True)
    return image


class OledView(QLabel):
    """Powiększony podgląd ekranu (piksele skalowane bez wygładzania)."""

    def __init__(self, scale: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scale = scale
        self.setFixedSize(QSize(WIDTH * scale + 8, HEIGHT * scale + 8))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#000; border:2px solid #222; border-radius:4px;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._last: Screen | None = None
        self.show_screen(Screen(kind="offline"))

    def show_screen(self, screen: Screen) -> None:
        if screen == self._last:
            return
        self._last = screen
        image = render(screen)
        if screen.kind != "off":
            # jasność OLED → przyciemnienie podglądu
            level = 0.45 + 0.55 * (screen.brightness / 255)
            if level < 0.99:
                painter = QPainter(image)
                painter.fillRect(image.rect(), QColor(0, 0, 0, int(255 * (1 - level))))
                painter.end()
        pix = QPixmap.fromImage(
            image.scaled(
                WIDTH * self._scale,
                HEIGHT * self._scale,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        self.setPixmap(pix)
