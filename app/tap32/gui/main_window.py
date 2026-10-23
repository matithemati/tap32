"""Okno główne: profile po lewej, wizualny Tap32 w centrum, edycja po prawej."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core.actions import ActionBase
from ..core.config import Profile, duplicate_profile, export_profile, import_profile
from ..core.engine import Controller
from ..core.logbuffer import LogEntry
from ..core.protocol import ENCODER_KEY, DeviceInfo
from ..core.simulator import Screen
from ..core.transport import list_all_ports
from .action_editor import EditorContext
from .bridge import QtBridge
from .device_view import DeviceView
from .editors import EncoderEditor, KeyEditor, ProfileEditor
from .icons import STATUS_COLORS, app_icon, dot_pixmap
from .log_view import LogView
from .settings_dialog import SettingsDialog


def running_processes() -> list[str]:
    names: set[str] = set()
    for p in psutil.process_iter(["name"]):
        name = p.info.get("name")
        if name and name.lower().endswith(".exe"):
            names.add(name)
    return sorted(names, key=str.lower)


class MainWindow(QMainWindow):
    def __init__(
        self,
        controller: Controller,
        bridge: QtBridge,
        screen_provider: Callable[[], Screen],
        apply_app_settings: Callable[[], None],
        log_entries: list[LogEntry],
    ) -> None:
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self.bridge = bridge
        self._screen_provider = screen_provider
        self._apply_app_settings = apply_app_settings
        self.quitting = False
        self.current_profile: Profile = controller.profiles.active
        self.current_key: int | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1280, 760)

        context = EditorContext(
            profile_names=self.config.profile_names,
            audio_processes=self._audio_processes,
            running_processes=running_processes,
            test_action=self._test_action,
        )

        # --- lewa kolumna: profile
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._profile_selected)
        self.profile_list.itemDoubleClicked.connect(self._activate_selected)
        buttons = QVBoxLayout()
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        for row, items in (
            (
                row1,
                (
                    ("Dodaj", self._add_profile),
                    ("Duplikuj", self._duplicate_profile),
                    ("Usuń", self._delete_profile),
                ),
            ),
            (
                row2,
                (
                    ("Zmień nazwę", self._rename_profile),
                    ("Import…", self._import_profile),
                    ("Eksport…", self._export_profile),
                ),
            ),
        ):
            for text, slot in items:
                b = QPushButton(text)
                b.clicked.connect(slot)
                row.addWidget(b)
        activate = QPushButton("Ustaw jako aktywny")
        activate.clicked.connect(self._activate_selected)
        buttons.addLayout(row1)
        buttons.addLayout(row2)
        buttons.addWidget(activate)
        left = QWidget()
        lv = QVBoxLayout(left)
        title = QLabel("Profile")
        title.setStyleSheet("font-weight:600; font-size: 12pt;")
        lv.addWidget(title)
        lv.addWidget(self.profile_list, 1)
        lv.addLayout(buttons)
        left.setMinimumWidth(230)

        # --- środek: urządzenie
        self.device_view = DeviceView()
        self.device_view.keySelected.connect(self._select_key)
        self.device_view.encoderSelected.connect(lambda: self._select_key(ENCODER_KEY))
        center = QWidget()
        cv = QVBoxLayout(center)
        self.center_title = QLabel()
        self.center_title.setStyleSheet("font-weight:600; font-size: 12pt;")
        back = QPushButton("Właściwości profilu")
        back.clicked.connect(lambda: self._select_key(None))
        top = QHBoxLayout()
        top.addWidget(self.center_title, 1)
        top.addWidget(back)
        cv.addLayout(top)
        cv.addWidget(self.device_view, 1)
        center.setMinimumWidth(440)

        # --- prawa kolumna: edytory
        self.profile_editor = ProfileEditor(running_processes)
        self.profile_editor.set_default_handlers(
            lambda p: p.name == self.config.default_profile, self._set_default
        )
        self.profile_editor.changed.connect(self._config_edited)
        self.profile_editor.renameRequested.connect(self._do_rename)
        self.key_editor = KeyEditor(context)
        self.key_editor.changed.connect(self._binding_edited)
        self.encoder_editor = EncoderEditor(context)
        self.encoder_editor.changed.connect(self._binding_edited)
        self.stack = QStackedWidget()
        for w in (self.profile_editor, self.key_editor, self.encoder_editor):
            self.stack.addWidget(w)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.stack)
        scroll.setMinimumWidth(420)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([250, 520, 500])

        self.log_view = LogView()
        for entry in log_entries:
            self.log_view.add(entry)
        tabs = QTabWidget()
        tabs.addTab(splitter, "Konfiguracja")
        tabs.addTab(self.log_view, "Dziennik")
        self.setCentralWidget(tabs)

        self._build_menu()
        self._build_status_bar()

        # Sygnały z kontrolera
        bridge.connectionChanged.connect(self._on_connection)
        bridge.rawInput.connect(self._on_raw_input)
        bridge.profileChanged.connect(self._on_profile_changed)
        bridge.actionFinished.connect(self._on_action_finished)
        bridge.logEntry.connect(self.log_view.add)

        # Odświeżanie podglądu OLED
        self._oled_timer = QTimer(self)
        self._oled_timer.setInterval(80)
        self._oled_timer.timeout.connect(
            lambda: self.device_view.oled.show_screen(self._screen_provider())
        )
        self._oled_timer.start()

        # Zmiany konfiguracji wysyłamy z opóźnieniem (np. pisanie etykiety)
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(300)
        self._apply_timer.timeout.connect(lambda: self.controller.config_changed())

        self.refresh_profiles()
        self._select_key(None)
        self._on_connection(False, None, None)

    # ------------------------------------------------------------------ menu i pasek stanu

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&Plik")
        for text, slot, shortcut in (
            ("Importuj profil…", self._import_profile, "Ctrl+I"),
            ("Eksportuj profil…", self._export_profile, "Ctrl+E"),
            ("Ustawienia…", self.open_settings, "Ctrl+,"),
        ):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        hide = QAction("Zamknij okno (działa w tle)", self)
        hide.triggered.connect(self.close)
        file_menu.addAction(hide)
        quit_action = QAction("Zakończ", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.request_quit)
        file_menu.addAction(quit_action)

        device = menu.addMenu("&Urządzenie")
        self.test_action = QAction("Tryb testu sprzętu", self)
        self.test_action.setCheckable(True)
        self.test_action.toggled.connect(self.controller.set_test_mode)
        device.addAction(self.test_action)
        device.addAction("Wyślij ponownie ekran i ustawienia", self.controller.push_device_state)
        device.addSeparator()
        device.addAction("Restart urządzenia", lambda: self._device_action("reboot"))
        device.addAction("Tryb wgrywania firmware…", lambda: self._device_action("bootloader"))
        self.bridge.testModeChanged.connect(self._sync_test_action)

        help_menu = menu.addMenu("Pomo&c")
        help_menu.addAction("O programie", self._about)

    def _sync_test_action(self, active: bool) -> None:
        self.test_action.blockSignals(True)
        self.test_action.setChecked(active)
        self.test_action.blockSignals(False)

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self.status_dot = QLabel()
        self.status_text = QLabel()
        self.status_board = QLabel()
        self.status_fw = QLabel()
        self.status_profile = QLabel()
        self.status_paused = QLabel()
        self.status_paused.setStyleSheet("color:#e67e22; font-weight:600;")
        bar.addWidget(self.status_dot)
        bar.addWidget(self.status_text)
        bar.addWidget(self._sep())
        bar.addWidget(self.status_board)
        bar.addWidget(self._sep())
        bar.addWidget(self.status_fw)
        bar.addWidget(self._sep())
        bar.addWidget(self.status_profile, 1)
        bar.addPermanentWidget(self.status_paused)

    @staticmethod
    def _sep() -> QLabel:
        label = QLabel("|")
        label.setStyleSheet("color: palette(mid);")
        return label

    # ------------------------------------------------------------------ profile

    def refresh_profiles(self) -> None:
        active = self.controller.profiles.active.name
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        current_row = 0
        for i, profile in enumerate(self.config.profiles):
            text = profile.name
            if profile.name == self.config.default_profile:
                text += "  (domyślny)"
            item = QListWidgetItem(("● " if profile.name == active else "   ") + text)
            if profile.name == active:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            if profile.processes:
                item.setToolTip("Automatycznie dla: " + ", ".join(profile.processes))
            self.profile_list.addItem(item)
            if profile is self.current_profile:
                current_row = i
        self.profile_list.setCurrentRow(current_row)
        self.profile_list.blockSignals(False)
        if self.current_profile not in self.config.profiles:
            self.current_profile = self.config.profiles[current_row]
        self.status_profile.setText(
            f"Profil: {active}" + (" (auto)" if self.controller.profiles.is_auto else "")
        )
        self._show_current()

    def _profile_selected(self, row: int) -> None:
        if 0 <= row < len(self.config.profiles):
            self.current_profile = self.config.profiles[row]
            self._show_current()

    def _show_current(self) -> None:
        self.center_title.setText(f"Profil: {self.current_profile.name}")
        self.device_view.set_profile(self.current_profile)
        self._select_key(self.current_key)

    def _select_key(self, key: int | None) -> None:
        self.current_key = key
        self.device_view.select(key)
        profile = self.current_profile
        if key is None:
            self.profile_editor.bind(profile)
            self.stack.setCurrentWidget(self.profile_editor)
        elif key == ENCODER_KEY:
            self.encoder_editor.bind(profile)
            self.stack.setCurrentWidget(self.encoder_editor)
        else:
            self.key_editor.bind(key, profile.keys[key])
            self.stack.setCurrentWidget(self.key_editor)

    def _selected_profile(self) -> Profile | None:
        row = self.profile_list.currentRow()
        return self.config.profiles[row] if 0 <= row < len(self.config.profiles) else None

    def _add_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Nowy profil", "Nazwa profilu:")
        if ok and name.strip():
            profile = Profile(name=self.config.unique_name(name.strip()))
            self.config.profiles = [*self.config.profiles, profile]
            self.current_profile = profile
            self._config_edited()
            self.refresh_profiles()

    def _duplicate_profile(self) -> None:
        source = self._selected_profile()
        if source is not None:
            copy = duplicate_profile(source, self.config)
            self.config.profiles = [*self.config.profiles, copy]
            self.current_profile = copy
            self._config_edited()
            self.refresh_profiles()

    def _rename_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        name, ok = QInputDialog.getText(self, "Zmień nazwę", "Nowa nazwa:", text=profile.name)
        if ok:
            self._do_rename(profile.name, name.strip())

    def _do_rename(self, old: str, new: str) -> None:
        if not new or new == old:
            return
        if self.config.profile(new) is not None:
            QMessageBox.warning(self, APP_NAME, f"Profil „{new}” już istnieje.")
            self.profile_editor.bind(self.current_profile)
            return
        self.controller.profiles.rename(old, new)
        self._config_edited()
        self.refresh_profiles()

    def _delete_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        if len(self.config.profiles) == 1:
            QMessageBox.information(self, APP_NAME, "Musi zostać co najmniej jeden profil.")
            return
        answer = QMessageBox.question(self, APP_NAME, f"Usunąć profil „{profile.name}”?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.config.profiles = [p for p in self.config.profiles if p is not profile]
        self.config.ensure_valid()
        self.current_profile = self.config.profiles[0]
        self.controller.profiles.refresh()
        self._config_edited()
        self.refresh_profiles()

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importuj profil", "", "Profil Tap32 (*.json)")
        if not path:
            return
        try:
            profile = import_profile(Path(path), self.config)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Nie udało się zaimportować profilu:\n{exc}")
            return
        self.config.profiles = [*self.config.profiles, profile]
        self.current_profile = profile
        self._config_edited()
        self.refresh_profiles()

    def _export_profile(self) -> None:
        profile = self._selected_profile() or self.current_profile
        path, _ = QFileDialog.getSaveFileName(
            self, "Eksportuj profil", f"{profile.name}.json", "Profil Tap32 (*.json)"
        )
        if path:
            try:
                export_profile(profile, Path(path))
            except OSError as exc:
                QMessageBox.warning(self, APP_NAME, f"Nie udało się zapisać:\n{exc}")

    def _activate_selected(self, *_: object) -> None:
        profile = self._selected_profile()
        if profile is not None:
            self.controller.call_soon(lambda: self.controller.profiles.set_active(profile.name))

    def _set_default(self, profile: Profile) -> None:
        self.config.default_profile = profile.name
        self.refresh_profiles()

    # ------------------------------------------------------------------ edycja

    def _binding_edited(self) -> None:
        self.device_view.set_profile(self.current_profile)
        self._apply_timer.start()

    def _config_edited(self) -> None:
        self._apply_timer.start()

    def _test_action(self, action: ActionBase) -> None:
        key = self.current_key if self.current_key and self.current_key != ENCODER_KEY else None
        self.controller.test_action(action, key)

    def _audio_processes(self) -> list[str]:
        try:
            return self.controller.platform.list_audio_processes()
        except Exception:
            return []

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config.settings, list_all_ports, self._device_action, self)
        if dialog.exec():
            self._apply_app_settings()
            self.controller.config_changed(device_settings=dialog.device_changed)
            if dialog.port_changed:
                set_port = getattr(self.controller.transport, "set_port", None)
                if set_port is not None:
                    set_port(self.config.settings.device.port)

    def _device_action(self, kind: str) -> None:
        if kind == "test":
            self.test_action.setChecked(not self.test_action.isChecked())
        elif kind == "reboot":
            self.controller.reboot_device(False)
        elif kind == "bootloader":
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "Przełączyć urządzenie w tryb wgrywania firmware?\n"
                "KB2040 pojawi się jako dysk RPI-RP2, XIAO ESP32-S3 – jako port pobierania.",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.controller.reboot_device(True)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"O programie {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br>Macropad 3×3 z pokrętłem i ekranem OLED.<br>"
            "Firmware: KB2040 (RP2040) / XIAO ESP32-S3.",
        )

    # ------------------------------------------------------------------ zdarzenia kontrolera

    def _on_connection(self, connected: bool, info: DeviceInfo | None, port: str | None) -> None:
        status = "connected" if connected else "disconnected"
        self.status_dot.setPixmap(dot_pixmap(STATUS_COLORS[status]))
        if connected and info is not None:
            self.status_text.setText(f"Połączono ({port})")
            self.status_board.setText(f"Płytka: {info.board_name}")
            self.status_fw.setText(f"Firmware: {info.fw} | OLED: {info.oled_status}")
            if info.has_diag and info.oled_addr is None:
                self.status_fw.setStyleSheet("color:#e74c3c; font-weight:600;")
                self.status_fw.setToolTip(
                    "Ekran nie odpowiada na I²C – szczegóły w zakładce Dziennik"
                )
            else:
                self.status_fw.setStyleSheet("")
                self.status_fw.setToolTip("")
        else:
            self.status_text.setText("Rozłączono – szukam Tap32…")
            self.status_board.setText("Płytka: —")
            self.status_fw.setText("Firmware: —")

    def _on_raw_input(self, key: int | None, down: bool, steps: int) -> None:
        if key is None:
            self.device_view.highlight_rotation(steps)
        else:
            self.device_view.highlight_key(key, down)

    def _on_profile_changed(self, profile: Profile, reason: str) -> None:
        if reason in ("manual", "auto", "auto-return") and not self.isActiveWindow():
            self.current_profile = self.controller.profiles.active
        self.refresh_profiles()

    def _on_action_finished(self, summary: str, error: object) -> None:
        if error is not None:
            self.statusBar().showMessage(f"Błąd: {summary} – {error}", 5000)

    def set_paused(self, paused: bool) -> None:
        self.status_paused.setText("AKCJE WSTRZYMANE" if paused else "")

    # ------------------------------------------------------------------ okno

    def request_quit(self) -> None:
        self.quitting = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.quitting:
            event.accept()
            return
        # Zamknięcie okna = minimalizacja do zasobnika
        event.ignore()
        self.hide()

    def show_and_raise(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()
