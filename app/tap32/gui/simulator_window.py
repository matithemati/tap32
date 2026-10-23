"""Okno symulatora Tap32: 9 klawiszy, pokrętło (kółko myszy), przycisk, podgląd OLED."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.simulator import SimulatedDevice
from .device_view import KnobWidget
from .icons import app_icon
from .oled import OledView


class SimKnob(KnobWidget):
    """Pokrętło: kółko myszy = obrót, lewy przycisk = wciśnięcie (klawisz 10)."""

    def __init__(self, device: SimulatedDevice) -> None:
        super().__init__()
        self.device = device
        self.setToolTip("Kółko myszy: obrót • Kliknij i przytrzymaj: przycisk pokrętła")

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        steps = 1 if delta > 0 else -1 if delta < 0 else 0
        if steps:
            self.device.rotate(steps)
            self.rotate(steps)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = True
            self.device.press(10)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = False
            self.device.release(10)
            self.update()


class SimulatorWindow(QWidget):
    def __init__(self, device: SimulatedDevice, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.device = device
        self.setWindowTitle("Tap32 – symulator urządzenia")
        self.setWindowIcon(app_icon("connected"))
        self.oled = OledView(scale=3)
        self.knob = SimKnob(device)

        top = QHBoxLayout()
        top.addWidget(self.oled)
        top.addStretch(1)
        top.addWidget(self.knob)

        grid = QGridLayout()
        for k in range(1, 10):
            button = QPushButton(f"K{k}")
            button.setMinimumSize(80, 64)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            button.pressed.connect(lambda k=k: device.press(k))
            button.released.connect(lambda k=k: device.release(k))
            grid.addWidget(button, (k - 1) // 3, (k - 1) % 3)

        enc_row = QHBoxLayout()
        for text, steps in (("⟲ w lewo", -1), ("w prawo ⟳", 1)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=steps: self._rotate(s))
            enc_row.addWidget(b)
        press = QPushButton("Przycisk pokrętła")
        press.pressed.connect(lambda: device.press(10))
        press.released.connect(lambda: device.release(10))
        enc_row.addWidget(press)

        self.status = QLabel()
        self.hid = QPlainTextEdit()
        self.hid.setReadOnly(True)
        self.hid.setMaximumHeight(80)
        self.hid.setPlaceholderText("Tryb awaryjny HID (offline): wysłane skróty pojawią się tutaj")

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(grid, 1)
        layout.addLayout(enc_row)
        layout.addWidget(self.status)
        layout.addWidget(self.hid)
        self.resize(460, 520)

        self._hid_count = 0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _rotate(self, steps: int) -> None:
        self.device.rotate(steps)
        self.knob.rotate(steps)

    def _refresh(self) -> None:
        self.oled.show_screen(self.device.screen())
        self.status.setText(
            f"Płytka: {self.device.board} • {'online' if self.device.online else 'OFFLINE (HID)'}"
        )
        if len(self.device.hid_log) != self._hid_count:
            for line in self.device.hid_log[self._hid_count :]:
                self.hid.appendPlainText(line)
            self._hid_count = len(self.device.hid_log)
