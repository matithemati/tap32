"""Okno ustawień: urządzenie, gesty, pokrętło, tryb awaryjny, aplikacja."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.actions import parse_hotkey
from ..core.config import FallbackEntry, Settings
from ..core.protocol import MEDIA_KEYS

FALLBACK_SLOTS = [(str(i), f"K{i}") for i in range(1, 10)] + [
    ("10", "Przycisk pokrętła"),
    ("enc_cw", "Pokrętło w prawo"),
    ("enc_ccw", "Pokrętło w lewo"),
]


def _spin(lo: int, hi: int, value: int, suffix: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    if suffix:
        s.setSuffix(suffix)
    return s


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        list_ports: Callable[[], list[tuple[str, str]]],
        on_device_action: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ustawienia – Tap32")
        self.settings = settings
        self.resize(620, 520)
        tabs = QTabWidget()

        # --- urządzenie
        d = settings.device
        dev = QWidget()
        f = QFormLayout(dev)
        self.port = QComboBox()
        self.port.addItem("Automatycznie (wykryj Tap32)", "auto")
        for device, description in list_ports():
            self.port.addItem(f"{device} – {description}", device)
        index = self.port.findData(d.port)
        if index < 0:
            self.port.addItem(d.port, d.port)
            index = self.port.count() - 1
        self.port.setCurrentIndex(index)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 255)
        self.brightness.setValue(d.brightness)
        self.screensaver = _spin(0, 65535, d.screensaver_s, " s")
        self.screensaver.setSpecialValueText("wyłączony")
        self.display_mode = QComboBox()
        self.display_mode.addItem("Siatka etykiet 3×3", "grid")
        self.display_mode.addItem("Duża nazwa profilu", "profile")
        self.display_mode.setCurrentIndex(max(0, self.display_mode.findData(d.display_mode)))
        self.flip = QCheckBox("Obróć ekran o 180°")
        self.flip.setChecked(d.flip)
        self.debounce = _spin(1, 50, d.debounce_ms, " ms")
        f.addRow("Port:", self.port)
        f.addRow("Jasność ekranu:", self.brightness)
        f.addRow("Wygaszacz po:", self.screensaver)
        f.addRow("Tryb ekranu:", self.display_mode)
        f.addRow("", self.flip)
        f.addRow("Debounce klawiszy:", self.debounce)
        buttons = QHBoxLayout()
        for text, key in (
            ("Tryb testu sprzętu", "test"),
            ("Restart urządzenia", "reboot"),
            ("Tryb wgrywania firmware", "bootloader"),
        ):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k=key: on_device_action(k))
            buttons.addWidget(b)
        f.addRow(buttons)
        tabs.addTab(dev, "Urządzenie")

        # --- gesty
        g = settings.gestures
        ges = QWidget()
        f = QFormLayout(ges)
        self.hold_ms = _spin(100, 5000, g.hold_ms, " ms")
        self.double_ms = _spin(100, 2000, g.double_tap_ms, " ms")
        self.hold_threshold = QCheckBox("Wykonuj „przytrzymanie” od razu po przekroczeniu progu")
        self.hold_threshold.setChecked(g.hold_on_threshold)
        f.addRow("Próg przytrzymania:", self.hold_ms)
        f.addRow("Okno podwójnego naciśnięcia:", self.double_ms)
        f.addRow("", self.hold_threshold)
        note = QLabel(
            "Jeśli klawisz nie ma akcji „podwójne”, zwykłe naciśnięcie wykonuje się od razu "
            "po puszczeniu. W przeciwnym razie czeka na upływ okna."
        )
        note.setWordWrap(True)
        f.addRow(note)
        tabs.addTab(ges, "Gesty")

        # --- pokrętło
        e = settings.encoder
        enc = QWidget()
        f = QFormLayout(enc)
        self.enc_reverse = QCheckBox("Odwróć kierunek obrotu")
        self.enc_reverse.setChecked(d.enc_reverse)
        self.enc_pulses = _spin(1, 8, d.enc_pulses)
        self.accel = QCheckBox("Przyspieszenie przy szybkim kręceniu")
        self.accel.setChecked(e.accel_enabled)
        self.accel_window = _spin(5, 500, e.accel_window_ms, " ms")
        self.accel_mult = _spin(1, 10, e.accel_multiplier, "×")
        f.addRow("", self.enc_reverse)
        f.addRow("Impulsy na ząbek:", self.enc_pulses)
        f.addRow("", self.accel)
        f.addRow("Szybki obrót, gdy odstęp ≤", self.accel_window)
        f.addRow("Mnożnik kroków:", self.accel_mult)
        tabs.addTab(enc, "Pokrętło")

        # --- tryb awaryjny
        fb = settings.fallback
        fall = QWidget()
        v = QVBoxLayout(fall)
        info = QLabel(
            "Gdy aplikacja nie działa (brak sygnału przez 3 s), Tap32 sam wysyła skróty "
            "klawiaturowe/multimedialne przez USB HID. Domyślnie są wyliczane z aktywnego "
            "profilu (akcje typu skrót i multimedia), a poniższe wpisy je nadpisują."
        )
        info.setWordWrap(True)
        self.fallback_from_profile = QCheckBox("Wyliczaj skróty z aktywnego profilu")
        self.fallback_from_profile.setChecked(fb.from_profile)
        self.fallback_table = QTableWidget(len(FALLBACK_SLOTS), 3)
        self.fallback_table.setHorizontalHeaderLabels(
            ["Element", "Skrót (np. ctrl+c)", "Multimedia"]
        )
        self.fallback_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fallback_table.verticalHeader().hide()
        custom: dict[str, FallbackEntry] = {c.slot: c for c in fb.custom}
        self._media_combos: list[QComboBox] = []
        self._hotkey_edits: list[QLineEdit] = []
        for row, (slot, label) in enumerate(FALLBACK_SLOTS):
            item = QTableWidgetItem(label)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.fallback_table.setItem(row, 0, item)
            entry = custom.get(slot)
            edit = QLineEdit(
                "+".join([*(entry.mods if entry else []), entry.code or ""]).strip("+")
                if entry and not entry.media
                else ""
            )
            edit.setPlaceholderText("(z profilu)")
            combo = QComboBox()
            combo.addItem("—", None)
            for media in MEDIA_KEYS:
                combo.addItem(media, media)
            combo.setCurrentIndex(max(0, combo.findData(entry.media if entry else None)))
            self.fallback_table.setCellWidget(row, 1, edit)
            self.fallback_table.setCellWidget(row, 2, combo)
            self._hotkey_edits.append(edit)
            self._media_combos.append(combo)
        self.fallback_error = QLabel()
        self.fallback_error.setStyleSheet("color:#e74c3c;")
        v.addWidget(info)
        v.addWidget(self.fallback_from_profile)
        v.addWidget(self.fallback_table, 1)
        v.addWidget(self.fallback_error)
        tabs.addTab(fall, "Tryb awaryjny")

        # --- aplikacja
        a = settings.app
        app = QWidget()
        f = QFormLayout(app)
        self.autostart = QCheckBox("Uruchamiaj z systemem Windows")
        self.autostart.setChecked(a.autostart)
        self.minimized = QCheckBox("Startuj zminimalizowana do zasobnika")
        self.minimized.setChecked(a.start_minimized)
        self.flash = QCheckBox("Pokazuj etykietę na ekranie po wykonaniu akcji")
        self.flash.setChecked(a.flash_on_action)
        self.auto_switch = QCheckBox("Automatycznie przełączaj profile według aktywnego okna")
        self.auto_switch.setChecked(a.auto_switch)
        self.theme = QComboBox()
        for key, label in (("system", "Według systemu"), ("light", "Jasny"), ("dark", "Ciemny")):
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(a.theme)))
        f.addRow("", self.autostart)
        f.addRow("", self.minimized)
        f.addRow("", self.flash)
        f.addRow("", self.auto_switch)
        f.addRow("Motyw:", self.theme)
        tabs.addTab(app, "Aplikacja")

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(box)
        self.device_changed = False
        self.port_changed = False

    def _fallback_entries(self) -> list[FallbackEntry] | None:
        entries = []
        for (slot, label), edit, combo in zip(
            FALLBACK_SLOTS, self._hotkey_edits, self._media_combos, strict=True
        ):
            media = combo.currentData()
            text = edit.text().strip()
            if media:
                entries.append(FallbackEntry(slot=slot, media=media))  # type: ignore[arg-type]
            elif text:
                try:
                    keys = parse_hotkey(text)
                except ValueError as exc:
                    self.fallback_error.setText(f"{label}: {exc}")
                    return None
                mods = [k for k in keys if k in ("ctrl", "shift", "alt", "win")]
                rest = [k for k in keys if k not in mods]
                if len(rest) > 1:
                    self.fallback_error.setText(f"{label}: tylko jeden klawisz poza modyfikatorami")
                    return None
                entries.append(FallbackEntry(slot=slot, mods=mods, code=rest[0] if rest else None))  # type: ignore[arg-type]
        return entries

    def _accept(self) -> None:
        entries = self._fallback_entries()
        if entries is None:
            return
        s = self.settings
        d = s.device
        before = d.model_dump()
        old_port = d.port
        d.port = self.port.currentData()
        d.brightness = self.brightness.value()
        d.screensaver_s = self.screensaver.value()
        d.display_mode = self.display_mode.currentData()
        d.flip = self.flip.isChecked()
        d.debounce_ms = self.debounce.value()
        d.enc_reverse = self.enc_reverse.isChecked()
        d.enc_pulses = self.enc_pulses.value()
        self.device_changed = d.model_dump() != before
        self.port_changed = d.port != old_port

        s.gestures.hold_ms = self.hold_ms.value()
        s.gestures.double_tap_ms = self.double_ms.value()
        s.gestures.hold_on_threshold = self.hold_threshold.isChecked()
        s.encoder.accel_enabled = self.accel.isChecked()
        s.encoder.accel_window_ms = self.accel_window.value()
        s.encoder.accel_multiplier = self.accel_mult.value()
        s.fallback.from_profile = self.fallback_from_profile.isChecked()
        s.fallback.custom = entries
        s.app.autostart = self.autostart.isChecked()
        s.app.start_minimized = self.minimized.isChecked()
        s.app.flash_on_action = self.flash.isChecked()
        s.app.auto_switch = self.auto_switch.isChecked()
        s.app.theme = self.theme.currentData()
        self.accept()
