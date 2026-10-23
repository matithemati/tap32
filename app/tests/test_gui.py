"""Test dymny GUI (offscreen): okno główne + symulator, edycja klawisza, podświetlanie."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("pytestqt")

from tap32.core.actions import make_action
from tap32.core.actions.builtin import HotkeyAction, MediaAction
from tap32.core.config import Config
from tap32.core.engine import Controller
from tap32.core.simulator import SimulatedDevice, SimulatorTransport
from tests.conftest import FakePlatform


@pytest.fixture
def window(qtbot, sync_executor):
    from tap32.gui.bridge import QtBridge
    from tap32.gui.main_window import MainWindow

    config = Config()
    config.ensure_valid()
    device = SimulatedDevice()
    transport = SimulatorTransport(device)
    platform = FakePlatform()
    controller = Controller(config, transport, platform, executor=sync_executor)
    bridge = QtBridge()
    controller.add_listener(bridge)
    win = MainWindow(controller, bridge, device.screen, lambda: None, [])
    qtbot.addWidget(win)
    controller.start()
    yield win, controller, device, platform
    controller.stop()


def test_main_window_edit_key(window, qtbot) -> None:
    win, controller, device, platform = window
    qtbot.waitUntil(lambda: controller.transport.connected, timeout=2000)

    win.device_view.tiles[5].clicked.emit(5)
    assert win.stack.currentWidget() is win.key_editor
    assert win.key_editor.label.edit.text() == "Kopiuj"

    # zmiana etykiety → konfiguracja i ekran urządzenia
    win.key_editor.label.edit.setText("Ctrl+C")
    assert controller.config.profiles[0].keys[5].label == "Ctrl+C"
    qtbot.waitUntil(
        lambda: device.screen().kind == "grid" and device.screen().labels[4] == "Ctrl+C",
        timeout=3000,
    )

    # zmiana akcji na multimedia przez edytor
    editor = win.key_editor.editors["tap"]
    editor.type_combo.setCurrentIndex(editor.type_combo.findData("media"))
    assert isinstance(controller.config.profiles[0].keys[5].tap, MediaAction)

    # fizyczne naciśnięcie (symulator) → akcja i podświetlenie
    device.press(5)
    qtbot.waitUntil(lambda: win.device_view.tiles[5].pressed_flash > 0, timeout=2000)
    device.release(5)
    qtbot.waitUntil(lambda: ("media", "play_pause") in platform.calls, timeout=2000)


def test_encoder_presets_and_hotkey_record(window, qtbot) -> None:
    from PySide6.QtCore import Qt

    win, controller, device, platform = window
    win.device_view.knob.clicked.emit()
    assert win.stack.currentWidget() is win.encoder_editor
    enc = win.encoder_editor
    enc.preset_combo.setCurrentIndex(enc.preset_combo.findData("zoom"))
    enc._apply_preset()
    cw = controller.config.profiles[0].encoder.rotate_cw
    assert isinstance(cw, HotkeyAction) and cw.keys == "ctrl+plus"

    # nagrywanie skrótu
    win.device_view.tiles[1].clicked.emit(1)
    editor = win.key_editor.editors["hold"]
    editor.type_combo.setCurrentIndex(editor.type_combo.findData("hotkey"))
    form_widget = editor.form.itemAt(0, editor.form.ItemRole.FieldRole).widget()
    form_widget.button.setChecked(True)
    qtbot.keyClick(
        form_widget.edit,
        Qt.Key.Key_E,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert form_widget.value() == "ctrl+shift+e"
    hold = controller.config.profiles[0].keys[1].hold
    assert isinstance(hold, HotkeyAction) and hold.keys == "ctrl+shift+e"


def test_profiles_panel(window, qtbot, monkeypatch) -> None:
    from PySide6.QtWidgets import QInputDialog

    win, controller, device, platform = window
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Gry", True))
    win._add_profile()
    assert controller.config.profile("Gry") is not None
    assert win.current_profile.name == "Gry"
    win._duplicate_profile()
    assert controller.config.profile("Gry – kopia") is not None
    controller.config.profile("Gry").keys[1].tap = make_action("hotkey", keys="f13")  # type: ignore[union-attr]
    win._do_rename("Gry", "Granie")
    assert controller.config.profile("Granie") is not None


def test_settings_dialog_roundtrip(window, qtbot) -> None:
    from tap32.gui.settings_dialog import SettingsDialog

    win, controller, device, platform = window
    dialog = SettingsDialog(controller.config.settings, lambda: [("COM3", "USB")], lambda k: None)
    dialog.brightness.setValue(10)
    dialog.hold_ms.setValue(700)
    dialog._hotkey_edits[0].setText("ctrl+alt+t")
    dialog._accept()
    s = controller.config.settings
    assert s.device.brightness == 10
    assert s.gestures.hold_ms == 700
    assert s.fallback.custom[0].mods == ["ctrl", "alt"] and s.fallback.custom[0].code == "t"
    assert dialog.device_changed


def test_oled_render_all_modes(qtbot) -> None:
    from tap32.core.simulator import Screen
    from tap32.gui.oled import render

    for screen in (
        Screen(kind="grid", title="Domyslny", labels=("Kalk",) * 9, online=True),
        Screen(kind="profile", title="Stream"),
        Screen(kind="bar", title="Vol", value=50),
        Screen(kind="text", line1="A", line2="B"),
        Screen(kind="flash", line1="Spotify", key=3),
        Screen(kind="test", test_keys=(True,) * 10, test_steps=3),
        Screen(kind="offline"),
        Screen(kind="off"),
    ):
        image = render(screen)
        assert image.width() == 128 and image.height() == 32
