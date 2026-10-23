"""Okno główne: pasek boczny (nawigacja, profile, urządzenie) i strony
Konfiguracja / Dziennik / Ustawienia.

Konfiguracja: podgląd Tap32 (ekran, pokrętło, klawisze) i panel edycji po prawej.
Zmiana języka przebudowuje interfejs (_build_ui) bez utraty stanu.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import psutil
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
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
from . import i18n, theme
from .action_editor import EditorContext
from .bridge import QtBridge
from .device_view import DeviceView
from .editors import EncoderEditor, KeyEditor, ProfileEditor
from .i18n import tr
from .icons import STATUS_COLORS, app_icon, app_pixmap, dot_pixmap
from .log_view import LogView
from .settings_dialog import SettingsDialog
from .widgets import Segmented, Switch, button, frame, label, styled


def running_processes() -> list[str]:
    names: set[str] = set()
    for p in psutil.process_iter(["name"]):
        name = p.info.get("name")
        if name and name.lower().endswith(".exe"):
            names.add(name)
    return sorted(names, key=str.lower)


def _menu_button(menu: QMenu, tooltip: str, icon_name: str = "dots-v") -> QToolButton:
    b = QToolButton()
    b.setIcon(theme.icon(icon_name))
    b.setIconSize(QSize(16, 16))
    b.setToolTip(tooltip)
    b.setMenu(menu)
    b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    styled(b, ghost=True)
    return b


class MainWindow(QMainWindow):
    pauseToggled = Signal(bool)

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
        self._page = "config"
        self._paused = False
        self._test_mode = False
        self._connection: tuple[bool, DeviceInfo | None, str | None] = (False, None, None)
        self._log_entries = list(log_entries)
        self._settings_dialog: SettingsDialog | None = None
        i18n.set_language(self.config.settings.app.language)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)

        self._build_actions()

        # Sygnały z kontrolera
        bridge.connectionChanged.connect(self._on_connection)
        bridge.rawInput.connect(self._on_raw_input)
        bridge.profileChanged.connect(self._on_profile_changed)
        bridge.actionFinished.connect(self._on_action_finished)
        bridge.logEntry.connect(self._on_log_entry)
        bridge.testModeChanged.connect(self._sync_test_action)

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

        # Chwilowe komunikaty o błędach akcji
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(5000)
        self._toast_timer.timeout.connect(lambda: self.toast.hide())

        self._build_ui()

    # ------------------------------------------------------------------ akcje (skróty klawiszowe)

    def _build_actions(self) -> None:
        def make(slot: Callable[[], object], shortcut: str | None = None) -> QAction:
            action = QAction(self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
                action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(lambda _=False: slot())
            self.addAction(action)
            return action

        self.import_action = make(self._import_profile, "Ctrl+I")
        self.export_action = make(self._export_profile, "Ctrl+E")
        self.settings_action = make(self.open_settings, "Ctrl+,")
        self.hide_action = make(self.close)
        self.about_action = make(self._about)
        self.quit_action = make(self.request_quit, "Ctrl+Q")
        self.resend_action = make(self.controller.push_device_state)
        self.reboot_action = make(lambda: self._device_action("reboot"))
        self.bootloader_action = make(lambda: self._device_action("bootloader"))
        self.test_action = QAction(self)
        self.test_action.setCheckable(True)
        self.test_action.toggled.connect(self.controller.set_test_mode)
        self.test_action.toggled.connect(self._test_mode_toggled)

    def _retranslate_actions(self) -> None:
        for action, text, icon_name in (
            (self.import_action, "Importuj profil…", "import"),
            (self.export_action, "Eksportuj profil…", "export"),
            (self.settings_action, "Ustawienia…", "sliders"),
            (self.hide_action, "Zamknij okno (działa w tle)", "window"),
            (self.about_action, "O programie", "info"),
            (self.quit_action, "Zakończ", "power"),
            (self.test_action, "Tryb testu sprzętu", "flask"),
            (self.resend_action, "Wyślij ponownie ekran i ustawienia", "refresh"),
            (self.reboot_action, "Restart urządzenia", "power"),
            (self.bootloader_action, "Tryb wgrywania firmware…", "download"),
        ):
            action.setText(tr(text))
            action.setIcon(theme.icon(icon_name))

    # ------------------------------------------------------------------ budowa interfejsu

    def _build_ui(self) -> None:
        if hasattr(self, "log_view"):
            self._log_entries = self.log_view.entries()
        self._retranslate_actions()

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(12, 12, 12, 12)
        h.setSpacing(12)
        h.addWidget(self._build_sidebar())
        h.addWidget(self._build_main(), 1)
        self.setCentralWidget(root)

        self.refresh_profiles()
        self._select_key(self.current_key)
        self._apply_connection()
        self.set_paused(self._paused)
        self._sync_test_action(self.test_action.isChecked())
        self._go(self._page if self._page != "settings" else "config")

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(256)
        v = QVBoxLayout(side)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        # logo + menu aplikacji
        app_menu = QMenu(self)
        for action in (self.import_action, self.export_action, self.settings_action):
            app_menu.addAction(action)
        app_menu.addSeparator()
        app_menu.addAction(self.hide_action)
        app_menu.addAction(self.about_action)
        app_menu.addSeparator()
        app_menu.addAction(self.quit_action)
        logo = QLabel()
        logo.setPixmap(app_pixmap(30))
        brand = QHBoxLayout()
        brand.setContentsMargins(4, 0, 0, 12)
        brand.setSpacing(10)
        brand.addWidget(logo)
        brand.addWidget(label(APP_NAME, "brand"))
        brand.addStretch(1)
        brand.addWidget(_menu_button(app_menu, tr("Menu aplikacji")))
        v.addLayout(brand)

        # nawigacja
        self.nav_group = QButtonGroup(self)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text, icon_name in (
            ("config", "Konfiguracja", "grid"),
            ("log", "Dziennik", "list"),
            ("settings", "Ustawienia", "sliders"),
        ):
            b = QPushButton(tr(text))
            b.setIcon(theme.icon(icon_name, "sub"))
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            styled(b, nav=True)
            if key == "settings":
                b.clicked.connect(self.open_settings)
            else:
                b.clicked.connect(lambda _=False, k=key: self._go(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            v.addWidget(b)
        self.log_badge = label("", "chip")
        self.log_badge.setStyleSheet(
            "background:#FDECEC; color:#A3241A; border-radius:6px;"
            " padding:1px 6px; font-weight:600;"
        )
        log_row = QHBoxLayout(self.nav_buttons["log"])
        log_row.setContentsMargins(0, 0, 10, 0)
        log_row.addStretch(1)
        log_row.addWidget(self.log_badge)

        line = frame("hline")
        v.addSpacing(10)
        v.addWidget(line)
        v.addSpacing(10)

        # profile
        head = QHBoxLayout()
        head.setContentsMargins(10, 0, 0, 4)
        head.addWidget(label(tr("Profile").upper(), "section"))
        head.addStretch(1)
        import_btn = button("", "import", ghost=True)
        import_btn.setToolTip(tr("Importuj profil…"))
        import_btn.clicked.connect(self._import_profile)
        add_btn = button("", "plus", ghost=True)
        add_btn.setToolTip(tr("Nowy profil"))
        add_btn.clicked.connect(self._add_profile)
        head.addWidget(import_btn)
        head.addWidget(add_btn)
        v.addLayout(head)

        self.profile_list = QListWidget()
        self.profile_list.setIconSize(QSize(10, 10))
        self.profile_list.currentRowChanged.connect(self._profile_selected)
        self.profile_list.itemDoubleClicked.connect(self._activate_selected)
        self.profile_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        v.addWidget(self.profile_list, 1)

        # język
        lang = QHBoxLayout()
        lang.setContentsMargins(6, 6, 2, 8)
        globe = QLabel()
        globe.setPixmap(theme.icon("globe", "sub").pixmap(16, 16))
        lang.addWidget(globe)
        lang.addWidget(label(tr("Język"), "muted"))
        lang.addStretch(1)
        self.language_switch = Segmented([("pl", "PL"), ("en", "EN")])
        self.language_switch.set_value(i18n.language())
        self.language_switch.changed.connect(self._set_language)
        lang.addWidget(self.language_switch)
        v.addLayout(lang)

        # karta urządzenia
        card = frame("card")
        ch = QHBoxLayout(card)
        ch.setContentsMargins(12, 12, 8, 12)
        ch.setSpacing(10)
        self.status_dot = QLabel()
        plug = QLabel()
        plug.setPixmap(theme.icon("plug", "sub", 18).pixmap(18, 18))
        plug_box = QVBoxLayout()
        plug_box.setSpacing(2)
        plug_box.addWidget(plug)
        plug_box.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignHCenter)
        plug_box.addStretch(1)
        ch.addLayout(plug_box)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        self.status_text = label("", "strong")
        self.status_board = label("", "muted", wrap=True)
        self.status_fw = label("", "muted", wrap=True)
        self.status_profile = label("", "muted", wrap=True)
        for w in (self.status_board, self.status_fw, self.status_profile):
            w.setStyleSheet("font-size: 8.5pt;")
        texts.addWidget(self.status_text)
        texts.addWidget(self.status_board)
        texts.addWidget(self.status_fw)
        texts.addWidget(self.status_profile)
        ch.addLayout(texts, 1)
        device_menu = QMenu(self)
        device_menu.addAction(self.test_action)
        device_menu.addAction(self.resend_action)
        device_menu.addSeparator()
        device_menu.addAction(self.reboot_action)
        device_menu.addAction(self.bootloader_action)
        ch.addWidget(_menu_button(device_menu, tr("Menu urządzenia")), 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(card)
        return side

    def _build_main(self) -> QWidget:
        main = frame("main")
        v = QVBoxLayout(main)
        v.setContentsMargins(24, 18, 24, 24)
        v.setSpacing(14)

        # pasek górny: ścieżka + wstrzymanie akcji
        top = QHBoxLayout()
        top.setSpacing(6)
        home = QLabel()
        home.setPixmap(theme.icon("home", "sub", 14).pixmap(14, 14))
        top.addWidget(home)
        top.addWidget(self._chevron())
        top.addWidget(label(APP_NAME, "crumb"))
        top.addWidget(self._chevron())
        self.crumb = label("", "crumbCur")
        top.addWidget(self.crumb)
        top.addStretch(1)
        self.toast = label("", "error")
        self.toast.hide()
        top.addWidget(self.toast)
        self.pause_switch = Switch(tr("Akcje włączone"))
        self.pause_switch.setChecked(True)
        self.pause_switch.toggled.connect(lambda on: self.pauseToggled.emit(not on))
        top.addWidget(self.pause_switch)
        v.addLayout(top)

        # banery stanu
        self.paused_banner = self._banner(
            "bannerWarn",
            "pause",
            "warn_text",
            tr("Akcje wstrzymane."),
            tr("Naciśnięcia klawiszy nie wykonują akcji."),
            tr("Wznów"),
            lambda: self.pauseToggled.emit(False),
        )
        self.test_banner = self._banner(
            "bannerInfo",
            "flask",
            "info_text",
            tr("Tryb testu sprzętu"),
            tr("Naciśnięcia tylko podświetlają elementy na podglądzie."),
            tr("Wyłącz"),
            lambda: self.test_action.setChecked(False),
        )
        v.addWidget(self.paused_banner)
        v.addWidget(self.test_banner)

        self.pages = QStackedWidget()
        self.config_page = self._build_config_page()
        self.log_view = LogView()
        for entry in self._log_entries:
            self.log_view.add(entry)
        self.log_view.errorCountChanged.connect(self._update_log_badge)
        self._update_log_badge(self.log_view.error_count())
        self.settings_host = QWidget()
        sl = QVBoxLayout(self.settings_host)
        sl.setContentsMargins(0, 0, 0, 0)
        for page in (self.config_page, self.log_view, self.settings_host):
            self.pages.addWidget(page)
        v.addWidget(self.pages, 1)
        return main

    def _chevron(self) -> QLabel:
        c = QLabel()
        c.setPixmap(theme.icon("chevron", "faint", 12).pixmap(12, 12))
        return c

    def _banner(
        self,
        name: str,
        icon_name: str,
        color_name: str,
        title: str,
        text: str,
        action_text: str,
        action: Callable[[], None],
    ) -> QFrame:
        banner = frame(name)
        h = QHBoxLayout(banner)
        h.setContentsMargins(14, 8, 10, 8)
        h.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(theme.icon(icon_name, color_name).pixmap(16, 16))
        h.addWidget(ic)
        h.addWidget(label(title, "strong"))
        h.addWidget(label(text), 1)
        b = button(action_text)
        b.clicked.connect(action)
        h.addWidget(b)
        banner.hide()
        return banner

    def _build_config_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(16)

        # nagłówek profilu
        head = QHBoxLayout()
        head.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(6)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.center_title = label("", "h1")
        self.active_chip = label(tr("Aktywny"), "chipOk")
        self.default_chip = label(tr("Domyślny"), "chip")
        title_row.addWidget(self.center_title)
        title_row.addWidget(self.active_chip)
        title_row.addWidget(self.default_chip)
        title_row.addStretch(1)
        titles.addLayout(title_row)
        titles.addWidget(
            label(
                tr(
                    "Kliknij klawisz lub pokrętło, aby edytować akcje. "
                    "Fizyczne naciśnięcia podświetlają elementy na żywo."
                ),
                "hint",
                wrap=True,
            )
        )
        head.addLayout(titles, 1)
        props = button(tr("Właściwości profilu"), "pencil")
        props.clicked.connect(lambda: self._select_key(None))
        profile_menu = QMenu(self)
        for text, icon_name, slot in (
            ("Dodaj", "plus", self._add_profile),
            ("Duplikuj", "copy", self._duplicate_profile),
            ("Zmień nazwę", "pencil", self._rename_profile),
            ("Eksportuj…", "export", self._export_profile),
        ):
            act = profile_menu.addAction(theme.icon(icon_name), tr(text))
            act.triggered.connect(lambda _=False, s=slot: s())
        profile_menu.addSeparator()
        delete = profile_menu.addAction(theme.icon("trash", "danger"), tr("Usuń"))
        delete.triggered.connect(lambda _=False: self._delete_profile())
        more = _menu_button(profile_menu, tr("Więcej akcji profilu"), "dots-h")
        styled(more, ghost=False)
        more.setFixedSize(36, 36)
        self.activate_button = button(tr("Ustaw jako aktywny"), primary=True)
        self.activate_button.clicked.connect(self._activate_selected)
        for w in (props, more, self.activate_button):
            head.addWidget(w, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(head)

        # karta: podgląd urządzenia + panel edycji
        context = EditorContext(
            profile_names=self.config.profile_names,
            audio_processes=self._audio_processes,
            running_processes=running_processes,
            test_action=self._test_action,
        )
        self.device_view = DeviceView()
        self.device_view.keySelected.connect(self._select_key)
        self.device_view.encoderSelected.connect(lambda: self._select_key(ENCODER_KEY))
        self.device_view.set_display_mode(self.config.settings.device.display_mode)

        self.profile_editor = ProfileEditor(running_processes)
        self.profile_editor.set_default_handlers(
            lambda p: p.name == self.config.default_profile, self._set_default
        )
        self.profile_editor.changed.connect(self._config_edited)
        self.profile_editor.renameRequested.connect(self._do_rename)
        self.key_editor = KeyEditor(context)
        self.key_editor.changed.connect(self._binding_edited)
        self.key_editor.closeRequested.connect(lambda: self._select_key(None))
        self.encoder_editor = EncoderEditor(context)
        self.encoder_editor.changed.connect(self._binding_edited)
        self.encoder_editor.closeRequested.connect(lambda: self._select_key(None))
        self.stack = QStackedWidget()
        for w in (self.profile_editor, self.key_editor, self.encoder_editor):
            self.stack.addWidget(w)

        card = frame("card")
        ch = QHBoxLayout(card)
        ch.setContentsMargins(1, 1, 1, 1)
        ch.setSpacing(0)
        pane = frame("devicePane")
        pl = QVBoxLayout(pane)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(self.device_view)
        ch.addWidget(pane, 1)
        inspector = frame("inspector")
        il = QVBoxLayout(inspector)
        il.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        hl = QVBoxLayout(host)
        hl.setContentsMargins(20, 20, 20, 20)
        hl.addWidget(self.stack)
        scroll.setWidget(host)
        il.addWidget(scroll)
        inspector.setFixedWidth(452)
        ch.addWidget(inspector)
        v.addWidget(card, 1)
        return page

    # ------------------------------------------------------------------ nawigacja i język

    def _go(self, page: str) -> None:
        self._page = page
        widget = {"config": self.config_page, "log": self.log_view, "settings": self.settings_host}[
            page
        ]
        self.pages.setCurrentWidget(widget)
        self.nav_buttons[page].setChecked(True)
        self._update_crumb()

    def _update_crumb(self) -> None:
        if self._page == "config":
            self.crumb.setText(f"{tr('Profile')} / {self.current_profile.name}")
        else:
            self.crumb.setText(tr("Dziennik") if self._page == "log" else tr("Ustawienia"))

    def _set_language(self, lang: str) -> None:
        if lang == i18n.language():
            return
        self.config.settings.app.language = lang  # type: ignore[assignment]
        i18n.set_language(lang)
        self.controller.config_changed()
        self._apply_app_settings()
        # przebudowa po zakończeniu obsługi kliknięcia (przycisk zostanie usunięty)
        QTimer.singleShot(0, self._build_ui)

    def _update_log_badge(self, count: int) -> None:
        self.log_badge.setText(str(count))
        self.log_badge.setVisible(count > 0)

    def _on_log_entry(self, entry: LogEntry) -> None:
        self.log_view.add(entry)

    # ------------------------------------------------------------------ stan urządzenia

    def _sync_test_action(self, active: bool) -> None:
        self.test_action.blockSignals(True)
        self.test_action.setChecked(active)
        self.test_action.blockSignals(False)
        self._test_mode_toggled(active)

    def _test_mode_toggled(self, active: bool) -> None:
        self._test_mode = active
        self.test_banner.setVisible(active)

    # ------------------------------------------------------------------ profile

    def refresh_profiles(self) -> None:
        active = self.controller.profiles.active.name
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        current_row = 0
        for i, profile in enumerate(self.config.profiles):
            text = profile.name
            if profile.name == self.config.default_profile:
                text += f"   · {tr('domyślny')}"
            item = QListWidgetItem(text)
            item.setIcon(
                dot_pixmap(
                    STATUS_COLORS["connected"] if profile.name == active else theme.color("faint"),
                    10,
                )
            )
            if profile.name == active:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            if profile.processes:
                item.setToolTip(tr("Automatycznie dla:") + " " + ", ".join(profile.processes))
            self.profile_list.addItem(item)
            if profile is self.current_profile:
                current_row = i
        self.profile_list.setCurrentRow(current_row)
        self.profile_list.blockSignals(False)
        if self.current_profile not in self.config.profiles:
            self.current_profile = self.config.profiles[current_row]
        self.status_profile.setText(
            f"{tr('Aktywny profil')}: {active}"
            + (" (auto)" if self.controller.profiles.is_auto else "")
        )
        self._show_current()

    def _profile_selected(self, row: int) -> None:
        if 0 <= row < len(self.config.profiles):
            self.current_profile = self.config.profiles[row]
            self._show_current()
            if self._page != "config":
                self._go("config")

    def _show_current(self) -> None:
        profile = self.current_profile
        is_active = profile.name == self.controller.profiles.active.name
        self.center_title.setText(profile.name)
        self.active_chip.setVisible(is_active)
        self.default_chip.setVisible(profile.name == self.config.default_profile)
        self.activate_button.setEnabled(not is_active)
        self.activate_button.setText(tr("Aktywny") if is_active else tr("Ustaw jako aktywny"))
        self.activate_button.setIcon(
            theme.icon("check", "sub") if is_active else theme.icon("play", "on_primary")
        )
        self.device_view.set_profile(profile)
        self._update_crumb()
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
        name, ok = QInputDialog.getText(self, tr("Nowy profil"), tr("Nazwa profilu:"))
        if ok and name.strip():
            profile = Profile(name=self.config.unique_name(name.strip()))
            self.config.profiles = [*self.config.profiles, profile]
            self.current_profile = profile
            self._config_edited()
            self.refresh_profiles()
            self._go("config")

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
        name, ok = QInputDialog.getText(
            self, tr("Zmień nazwę"), tr("Nowa nazwa:"), text=profile.name
        )
        if ok:
            self._do_rename(profile.name, name.strip())

    def _do_rename(self, old: str, new: str) -> None:
        if not new or new == old:
            return
        if self.config.profile(new) is not None:
            QMessageBox.warning(
                self, APP_NAME, tr("Profil „{name}” już istnieje.").format(name=new)
            )
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
            QMessageBox.information(self, APP_NAME, tr("Musi zostać co najmniej jeden profil."))
            return
        answer = QMessageBox.question(
            self, APP_NAME, tr("Usunąć profil „{name}”?").format(name=profile.name)
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.config.profiles = [p for p in self.config.profiles if p is not profile]
        self.config.ensure_valid()
        self.current_profile = self.config.profiles[0]
        self.controller.profiles.refresh()
        self._config_edited()
        self.refresh_profiles()

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Importuj profil"), "", tr("Profil Tap32 (*.json)")
        )
        if not path:
            return
        try:
            profile = import_profile(Path(path), self.config)
        except Exception as exc:
            QMessageBox.warning(
                self, APP_NAME, tr("Nie udało się zaimportować profilu:") + f"\n{exc}"
            )
            return
        self.config.profiles = [*self.config.profiles, profile]
        self.current_profile = profile
        self._config_edited()
        self.refresh_profiles()

    def _export_profile(self) -> None:
        profile = self._selected_profile() or self.current_profile
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Eksportuj profil"), f"{profile.name}.json", tr("Profil Tap32 (*.json)")
        )
        if path:
            try:
                export_profile(profile, Path(path))
            except OSError as exc:
                QMessageBox.warning(self, APP_NAME, tr("Nie udało się zapisać:") + f"\n{exc}")

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
        """Strona ustawień (formularz budowany od nowa przy każdym otwarciu)."""
        if self._settings_dialog is not None:
            self._settings_dialog.deleteLater()
        dialog = SettingsDialog(self.config.settings, list_all_ports, self._device_action)
        dialog.embed()
        dialog.accepted.connect(lambda: self._settings_accepted(dialog))
        dialog.rejected.connect(lambda: self._go("config"))
        self.settings_host.layout().addWidget(dialog)
        dialog.show()
        self._settings_dialog = dialog
        self._go("settings")

    def _settings_accepted(self, dialog: SettingsDialog) -> None:
        self._apply_app_settings()
        self.controller.config_changed(device_settings=dialog.device_changed)
        if dialog.port_changed:
            set_port = getattr(self.controller.transport, "set_port", None)
            if set_port is not None:
                set_port(self.config.settings.device.port)
        self.device_view.set_display_mode(self.config.settings.device.display_mode)
        self._settings_dialog = None
        dialog.deleteLater()
        self._page = "config"
        if dialog.language_changed:
            i18n.set_language(self.config.settings.app.language)
        # motyw lub język mogły się zmienić – ikony i teksty budujemy od nowa
        QTimer.singleShot(0, self._build_ui)

    def _device_action(self, kind: str) -> None:
        if kind == "test":
            self.test_action.setChecked(not self.test_action.isChecked())
        elif kind == "reboot":
            self.controller.reboot_device(False)
        elif kind == "bootloader":
            answer = QMessageBox.question(
                self,
                APP_NAME,
                tr(
                    "Przełączyć urządzenie w tryb wgrywania firmware?\n"
                    "KB2040 pojawi się jako dysk RPI-RP2, XIAO ESP32-S3 – jako port pobierania."
                ),
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.controller.reboot_device(True)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"{tr('O programie')} {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br>"
            + tr("Macropad 3×3 z pokrętłem i ekranem OLED.")
            + "<br>Firmware: KB2040 (RP2040) / XIAO ESP32-S3.",
        )

    # ------------------------------------------------------------------ zdarzenia kontrolera

    def _on_connection(self, connected: bool, info: DeviceInfo | None, port: str | None) -> None:
        self._connection = (connected, info, port)
        self._apply_connection()

    def _apply_connection(self) -> None:
        connected, info, port = self._connection
        status = "connected" if connected else "disconnected"
        self.status_dot.setPixmap(dot_pixmap(STATUS_COLORS[status], 10))
        if connected and info is not None:
            self.status_text.setText(f"{tr('Połączono')} · {port}")
            self.status_board.setText(f"{tr('Płytka')}: {info.board_name}")
            self.status_fw.setText(f"Firmware: {info.fw} · OLED: {info.oled_status}")
            if info.has_diag and info.oled_addr is None:
                self.status_fw.setStyleSheet(
                    f"font-size: 8.5pt; color: {theme.tokens()['danger']}; font-weight: 600;"
                )
                self.status_fw.setToolTip(
                    tr("Ekran nie odpowiada na I²C – szczegóły w zakładce Dziennik")
                )
            else:
                self.status_fw.setStyleSheet("font-size: 8.5pt;")
                self.status_fw.setToolTip("")
        else:
            self.status_text.setText(tr("Rozłączono"))
            self.status_board.setText(tr("Szukam Tap32…"))
            self.status_fw.setText(f"{tr('Płytka')}: — · Firmware: —")
            self.status_fw.setStyleSheet("font-size: 8.5pt;")
            self.status_fw.setToolTip("")

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
            self.toast.setText(f"{tr('Błąd')}: {summary} – {error}")
            self.toast.show()
            self._toast_timer.start()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.pause_switch.blockSignals(True)
        self.pause_switch.setChecked(not paused)
        self.pause_switch.setText(tr("Akcje wstrzymane") if paused else tr("Akcje włączone"))
        self.pause_switch.updateGeometry()
        self.pause_switch.blockSignals(False)
        self.paused_banner.setVisible(paused)

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
