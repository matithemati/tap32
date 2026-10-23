"""Ikony rysowane w kodzie (bez plików graficznych)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

STATUS_COLORS = {
    "connected": QColor("#2ecc71"),
    "connecting": QColor("#f1c40f"),
    "disconnected": QColor("#e74c3c"),
    "paused": QColor("#95a5a6"),
}


def app_pixmap(size: int = 256, status: str | None = None) -> QPixmap:
    """Logo Tap32: zaokrąglony kwadrat z siatką 3×3 i pokrętłem."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 64
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1f2933"))
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 12 * s, 12 * s)
    # ekran
    p.setBrush(QColor("#0b0f14"))
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 30 * s, 10 * s), 2 * s, 2 * s)
    p.setBrush(QColor("#4fc3f7"))
    p.drawRect(QRectF(11 * s, 12 * s, 18 * s, 2 * s))
    # pokrętło
    p.setBrush(QColor("#9aa5b1"))
    p.drawEllipse(QRectF(43 * s, 6 * s, 14 * s, 14 * s))
    p.setBrush(QColor("#1f2933"))
    p.drawRect(QRectF(49.2 * s, 7 * s, 1.6 * s, 5 * s))
    # klawisze
    colors = ["#f57c00", "#4fc3f7", "#66bb6a"]
    for r in range(3):
        for c in range(3):
            p.setBrush(QColor(colors[(r + c) % 3]) if (r, c) == (0, 0) else QColor("#e4e7eb"))
            p.drawRoundedRect(
                QRectF((9 + c * 16) * s, (24 + r * 12.5) * s, 13 * s, 10 * s), 2 * s, 2 * s
            )
    if status is not None:
        color = STATUS_COLORS.get(status, QColor("#95a5a6"))
        p.setBrush(color)
        p.setPen(QPen(QColor("#ffffff"), 2.5 * s))
        p.drawEllipse(QRectF(40 * s, 40 * s, 22 * s, 22 * s))
    p.end()
    return pix


def app_icon(status: str | None = None) -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size, status))
    return icon


def dot_pixmap(color: QColor, size: int = 12) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return pix


def text_icon(text: str, color: str = "#4fc3f7", size: int = 32) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(color))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 0.7))
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return QIcon(pix)
