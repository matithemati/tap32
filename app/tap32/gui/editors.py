"""Panele edycji: klawisz, pokrętło, profil."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.actions import ActionBase, make_action
from ..core.config import KeyBinding, Profile
from ..core.protocol import ENCODER_KEY, LABEL_CHARS, transliterate
from . import theme
from .action_editor import ActionEditor, EditorContext
from .i18n import tr
from .widgets import Segmented, Switch, button, combo, frame, hline, label, styled

GESTURE_TABS = (("tap", "Naciśnięcie"), ("hold", "Przytrzymanie"), ("double_tap", "Podwójne"))

SWATCHES = (
    "#2e7d32",
    "#1565c0",
    "#ef6c00",
    "#6a1b9a",
    "#37474f",
    "#c62828",
    "#00838f",
    "#4527a0",
    "#ad1457",
    "#455a64",
)


def inspector_header(
    kicker: str, title: QLabel, badge: QLabel | None = None
) -> tuple[QHBoxLayout, QPushButton]:
    """Nagłówek panelu: znaczek, nadtytuł, tytuł i przycisk zamknięcia."""
    row = QHBoxLayout()
    row.setSpacing(10)
    if badge is not None:
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(0)
    col.addWidget(label(kicker.upper(), "kicker"))
    col.addWidget(title)
    row.addLayout(col, 1)
    close = button("", "x", ghost=True)
    close.setToolTip(tr("Zamknij"))
    close.setFixedSize(32, 32)
    row.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
    return row, close


def _badge_style(badge: QLabel, color: str) -> None:
    c = QColor(color)
    # ciemne kolory klawiszy byłyby nieczytelne na ciemnym tle
    text = theme.tokens()["text"] if theme.is_dark() and c.lightness() < 110 else color
    badge.setStyleSheet(
        f"background: rgba({c.red()},{c.green()},{c.blue()},60); color: {text}; "
        "border-radius: 11px; font-weight: 700;"
    )


class LabelEdit(QWidget):
    """Etykieta z licznikiem znaków (OLED: 7 znaków) i podglądem tekstu na ekranie."""

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.setMaxLength(LABEL_CHARS)
        self.edit.setPlaceholderText(tr("np. Spotify"))
        self.counter = label("", "muted")
        self.preview = label("", "oledPreview")
        head = QHBoxLayout()
        head.addWidget(label(tr("Etykieta"), "lbl"))
        head.addStretch(1)
        head.addWidget(self.counter)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addWidget(label(tr("Na ekranie:"), "muted"))
        foot.addWidget(self.preview)
        foot.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(head)
        layout.addWidget(self.edit)
        layout.addLayout(foot)
        self.edit.textChanged.connect(self._changed)
        self._changed(self.edit.text(), emit=False)

    def set_text(self, text: str) -> None:
        self.edit.blockSignals(True)
        self.edit.setText(text)
        self.edit.blockSignals(False)
        self._changed(text, emit=False)

    def _changed(self, text: str, emit: bool = True) -> None:
        self.counter.setText(f"{len(text)}/{LABEL_CHARS}")
        self.preview.setText(transliterate(text) or "—")
        if emit:
            self.changed.emit(text)


class ColorButton(QWidget):
    """Paleta kolorów klawisza + kolor własny."""

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = "#455a64"
        self._swatches: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        row.setSpacing(5)
        for c in SWATCHES:
            b = QPushButton()
            b.setFixedSize(24, 24)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(c)
            b.clicked.connect(lambda _=False, col=c: self._set(col))
            self._swatches[c] = b
            row.addWidget(b)
        self.custom = QPushButton(tr("Własny…"))
        self.custom.clicked.connect(self._pick)
        row.addWidget(self.custom)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(label(tr("Kolor"), "lbl"))
        layout.addLayout(row)
        self._refresh()

    def set_color(self, color: str) -> None:
        self._color = color
        self._refresh()

    def color(self) -> str:
        return self._color

    def _refresh(self) -> None:
        ring = theme.tokens()["text"]
        for c, b in self._swatches.items():
            selected = c.lower() == self._color.lower()
            b.setStyleSheet(
                f"QPushButton {{ background: {c}; border-radius: 7px; padding: 0; min-height: 0;"
                f" border: 2px solid {ring if selected else 'transparent'}; }}"
            )
        custom = self._color.lower() not in self._swatches
        self.custom.setStyleSheet(
            f"QPushButton {{ border: 2px solid {self._color}; }}" if custom else ""
        )

    def _set(self, color: str) -> None:
        self._color = color
        self._refresh()
        self.changed.emit(color)

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, tr("Kolor klawisza"))
        if color.isValid():
            self._set(color.name())


class KeyEditor(QWidget):
    """Etykieta, kolor i akcje gestów tap / hold / double_tap jednego klawisza."""

    changed = Signal()
    closeRequested = Signal()

    def __init__(self, context: EditorContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.binding: KeyBinding | None = None
        self.title = label("", "h2")
        self.badge = label("", "badge")
        self.badge.setFixedSize(40, 40)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header = QWidget()
        head, close = inspector_header(tr("Klawisz"), self.title, self.badge)
        head.setContentsMargins(0, 0, 0, 0)
        self.header.setLayout(head)
        close.clicked.connect(self.closeRequested)

        self.label = LabelEdit()
        self.color = ColorButton()
        self.label.changed.connect(self._label_changed)
        self.color.changed.connect(self._color_changed)

        self.gesture_bar = Segmented([(g, tr(t)) for g, t in GESTURE_TABS])
        self.gesture_bar.changed.connect(self._show_gesture)
        self.gesture_stack = QStackedWidget()
        self.editors: dict[str, ActionEditor] = {}
        for gesture, _title in GESTURE_TABS:
            editor = ActionEditor(context)
            editor.changed.connect(lambda g=gesture: self._action_changed(g))
            self.editors[gesture] = editor
            self.gesture_stack.addWidget(editor)
        self.gesture_bar.set_value("tap")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.header)
        layout.addWidget(self.label)
        layout.addWidget(self.color)
        layout.addWidget(self.gesture_bar, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hline())
        layout.addWidget(self.gesture_stack, 1)

    def bind(self, key: int, binding: KeyBinding) -> None:
        self.binding = binding
        self.title.setText(
            f"{tr('Klawisz')} K{key}" if key != ENCODER_KEY else tr("Przycisk pokrętła")
        )
        self.badge.setText(f"K{key}" if key != ENCODER_KEY else "◎")
        self.label.set_text(binding.label)
        self.color.set_color(binding.color)
        _badge_style(self.badge, binding.color)
        for gesture, editor in self.editors.items():
            editor.set_action(binding.action_for(gesture))
        self._update_tab_titles()

    def _show_gesture(self, gesture: str) -> None:
        self.gesture_stack.setCurrentWidget(self.editors[gesture])

    def _update_tab_titles(self) -> None:
        if self.binding is None:
            return
        for gesture, title in GESTURE_TABS:
            mark = "  ●" if self.binding.action_for(gesture) else ""
            self.gesture_bar.set_text(gesture, tr(title) + mark)

    def _label_changed(self, text: str) -> None:
        if self.binding is not None:
            self.binding.label = text
            self.changed.emit()

    def _color_changed(self, color: str) -> None:
        if self.binding is not None:
            self.binding.color = color
            _badge_style(self.badge, color)
            self.changed.emit()

    def _action_changed(self, gesture: str) -> None:
        if self.binding is not None:
            self.binding.set_action(gesture, self.editors[gesture].action())
            self._update_tab_titles()
            self.changed.emit()


ENCODER_TABS = (
    ("rotate_cw", "W prawo"),
    ("rotate_ccw", "W lewo"),
    ("press_rotate_cw", "Wciśnięte + w prawo"),
    ("press_rotate_ccw", "Wciśnięte + w lewo"),
)


def _preset_actions(name: str, process: str = "") -> dict[str, ActionBase | None]:
    if name == "system_volume":
        return {
            "rotate_cw": make_action("media", key="vol_up"),
            "rotate_ccw": make_action("media", key="vol_down"),
        }
    if name == "app_volume":
        return {
            "rotate_cw": make_action("app_volume", process=process, mode="up"),
            "rotate_ccw": make_action("app_volume", process=process, mode="down"),
        }
    if name == "scroll":
        return {
            "rotate_cw": make_action("scroll", direction="down", lines=3),
            "rotate_ccw": make_action("scroll", direction="up", lines=3),
        }
    if name == "hscroll":
        return {
            "rotate_cw": make_action("scroll", direction="right", lines=3),
            "rotate_ccw": make_action("scroll", direction="left", lines=3),
        }
    if name == "zoom":
        return {
            "rotate_cw": make_action("hotkey", keys="ctrl+plus"),
            "rotate_ccw": make_action("hotkey", keys="ctrl+-"),
        }
    if name == "tracks":
        return {
            "rotate_cw": make_action("media", key="next"),
            "rotate_ccw": make_action("media", key="prev"),
        }
    if name == "profiles":
        return {
            "rotate_cw": make_action("profile", mode="next"),
            "rotate_ccw": make_action("profile", mode="prev"),
        }
    return {}


PRESETS = (
    ("system_volume", "Głośność systemu"),
    ("app_volume", "Głośność programu…"),
    ("scroll", "Przewijanie pionowe"),
    ("hscroll", "Przewijanie poziome"),
    ("zoom", "Zoom (Ctrl +/−)"),
    ("tracks", "Utwory (następny/poprzedni)"),
    ("profiles", "Zmiana profilu"),
)


class EncoderEditor(QWidget):
    """Obroty (zwykłe i z wciśniętym przyciskiem), gesty przycisku i szybkie presety."""

    changed = Signal()
    closeRequested = Signal()

    def __init__(self, context: EditorContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.profile: Profile | None = None
        badge = label("◎", "badge")
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _badge_style(badge, theme.tokens()["accent"])
        head, close = inspector_header(tr("Pokrętło"), label(tr("Pokrętło"), "h2"), badge)
        close.clicked.connect(self.closeRequested)

        presets = frame("soft")
        self.preset_combo = combo()
        for key, text in PRESETS:
            self.preset_combo.addItem(tr(text), key)
        self.preset_target = combo()
        self.preset_target.addItem(tr("Obrót bez wciśnięcia"), "")
        self.preset_target.addItem(tr("Obrót z wciśniętym przyciskiem"), "press_")
        self.process_combo = combo()
        self.process_combo.setEditable(True)
        self.process_combo.lineEdit().setPlaceholderText(tr("proces, np. spotify.exe"))
        apply = button(tr("Zastosuj"), primary=True)
        apply.clicked.connect(self._apply_preset)
        self.preset_combo.currentIndexChanged.connect(self._preset_changed)
        grid = QGridLayout(presets)
        grid.setContentsMargins(14, 12, 14, 14)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(label(tr("Szybkie presety"), "strong"), 0, 0, 1, 2)
        grid.addWidget(self.preset_target, 1, 0)
        grid.addWidget(self.preset_combo, 1, 1)
        grid.addWidget(self.process_combo, 2, 0)
        grid.addWidget(apply, 2, 1, Qt.AlignmentFlag.AlignRight)
        self._preset_changed()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.editors: dict[str, ActionEditor] = {}
        for gesture, text in ENCODER_TABS:
            editor = ActionEditor(context)
            editor.changed.connect(lambda g=gesture: self._action_changed(g))
            self.editors[gesture] = editor
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(0, 14, 0, 0)
            pl.addWidget(editor)
            self.tabs.addTab(page, tr(text))

        self.button_editor = KeyEditor(context)
        self.button_editor.header.hide()
        self.button_editor.changed.connect(self.changed)
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 14, 0, 0)
        pl.addWidget(self.button_editor)
        self.tabs.addTab(page, tr("Przycisk"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(head)
        layout.addWidget(presets)
        layout.addWidget(self.tabs, 1)

    def bind(self, profile: Profile) -> None:
        self.profile = profile
        for gesture, editor in self.editors.items():
            editor.set_action(profile.encoder.action_for(gesture))
        self.button_editor.bind(ENCODER_KEY, profile.keys[ENCODER_KEY])
        self._update_tab_titles()

    def _update_tab_titles(self) -> None:
        if self.profile is None:
            return
        for i, (gesture, text) in enumerate(ENCODER_TABS):
            mark = " ●" if self.profile.encoder.action_for(gesture) else ""
            self.tabs.setTabText(i, tr(text) + mark)

    def _action_changed(self, gesture: str) -> None:
        if self.profile is not None:
            self.profile.encoder.set_action(gesture, self.editors[gesture].action())
            self._update_tab_titles()
            self.changed.emit()

    def _preset_changed(self) -> None:
        is_app = self.preset_combo.currentData() == "app_volume"
        self.process_combo.setVisible(is_app)
        if is_app and self.process_combo.count() == 0:
            self.process_combo.addItems(self.context.audio_processes())

    def _apply_preset(self) -> None:
        if self.profile is None:
            return
        prefix = self.preset_target.currentData()
        actions = _preset_actions(
            self.preset_combo.currentData(), self.process_combo.currentText().strip()
        )
        for gesture, action in actions.items():
            self.profile.encoder.set_action(prefix + gesture, action)
        self.bind(self.profile)
        self.changed.emit()


class ProfileEditor(QWidget):
    """Nazwa, profil domyślny i procesy do automatycznego przełączania."""

    changed = Signal()
    renameRequested = Signal(str, str)  # stara, nowa nazwa

    def __init__(
        self, running_processes: Callable[[], list[str]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.profile: Profile | None = None
        self._running = running_processes
        self.name = QLineEdit()
        self.name.editingFinished.connect(self._rename)
        self.default = Switch(tr("Profil domyślny (start aplikacji)"))
        self.default.toggled.connect(self._default_toggled)
        self._is_default_cb: Callable[[Profile], bool] = lambda p: False
        self._set_default_cb: Callable[[Profile], None] = lambda p: None

        group = frame("outlined")
        self.processes = QListWidget()
        self.processes.setObjectName("boxed")
        self.processes.setMinimumHeight(140)
        self.add_combo = combo()
        self.add_combo.setEditable(True)
        self.add_combo.lineEdit().setPlaceholderText(tr("np. obs64.exe"))
        self.add_combo.setMinimumContentsLength(10)
        refresh = button("", "refresh")
        refresh.setToolTip(tr("Odśwież listę uruchomionych procesów"))
        refresh.setFixedWidth(36)
        refresh.clicked.connect(self._refresh_running)
        add = button(tr("Dodaj"), primary=True)
        add.clicked.connect(self._add_process)
        remove = button(tr("Usuń"))
        remove.clicked.connect(self._remove_process)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.add_combo, 1)
        row.addWidget(refresh)
        row.addWidget(add)
        row.addWidget(remove)
        g = QVBoxLayout(group)
        g.setContentsMargins(14, 12, 14, 14)
        g.setSpacing(8)
        g.addWidget(label(tr("Automatyczne przełączanie"), "strong"))
        g.addWidget(
            label(
                tr("Profil włącza się, gdy aktywne jest okno jednego z tych procesów."),
                "hint",
                wrap=True,
            )
        )
        g.addWidget(self.processes, 1)
        g.addLayout(row)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(label(tr("Profil").upper(), "kicker"))
        title_col.addWidget(label(tr("Właściwości profilu"), "h2"))

        name_col = QVBoxLayout()
        name_col.setSpacing(6)
        name_col.addWidget(label(tr("Nazwa"), "lbl"))
        name_col.addWidget(self.name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(title_col)
        layout.addLayout(name_col)
        layout.addWidget(self.default)
        layout.addWidget(group, 1)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def set_default_handlers(
        self, is_default: Callable[[Profile], bool], set_default: Callable[[Profile], None]
    ) -> None:
        self._is_default_cb = is_default
        self._set_default_cb = set_default

    def bind(self, profile: Profile) -> None:
        self.profile = profile
        self.name.setText(profile.name)
        self.default.blockSignals(True)
        self.default.setChecked(self._is_default_cb(profile))
        self.default.setEnabled(not self.default.isChecked())
        self.default.blockSignals(False)
        self.processes.clear()
        self.processes.addItems(profile.processes)

    def _rename(self) -> None:
        if self.profile is None:
            return
        new = self.name.text().strip()
        if new and new != self.profile.name:
            self.renameRequested.emit(self.profile.name, new)

    def _default_toggled(self, checked: bool) -> None:
        if checked and self.profile is not None:
            self._set_default_cb(self.profile)
            self.default.setEnabled(False)
            self.changed.emit()

    def _refresh_running(self) -> None:
        current = self.add_combo.currentText()
        self.add_combo.clear()
        self.add_combo.addItems(self._running())
        self.add_combo.setCurrentText(current)

    def _add_process(self) -> None:
        name = self.add_combo.currentText().strip()
        if not name or self.profile is None:
            return
        if not name.lower().endswith(".exe"):
            name += ".exe"
        if name.lower() not in (p.lower() for p in self.profile.processes):
            self.profile.processes = [*self.profile.processes, name]
            self.processes.addItem(name)
            self.changed.emit()

    def _remove_process(self) -> None:
        row = self.processes.currentRow()
        if row < 0 or self.profile is None:
            return
        processes = list(self.profile.processes)
        del processes[row]
        self.profile.processes = processes
        self.processes.takeItem(row)
        self.changed.emit()


__all__ = ["ColorButton", "EncoderEditor", "KeyEditor", "LabelEdit", "ProfileEditor", "styled"]
