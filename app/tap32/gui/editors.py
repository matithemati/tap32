"""Panele edycji: klawisz, pokrętło, profil."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.actions import ActionBase, make_action
from ..core.config import KeyBinding, Profile
from ..core.protocol import ENCODER_KEY, LABEL_CHARS, transliterate
from .action_editor import ActionEditor, EditorContext

GESTURE_TABS = (("tap", "Naciśnięcie"), ("hold", "Przytrzymanie"), ("double_tap", "Podwójne"))


class LabelEdit(QWidget):
    """Etykieta z licznikiem znaków (OLED: 7 znaków)."""

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.setMaxLength(LABEL_CHARS)
        self.edit.setPlaceholderText("np. Spotify")
        self.counter = QLabel()
        self.counter.setMinimumWidth(48)
        self.preview = QLabel()
        self.preview.setStyleSheet("color: palette(mid);")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.counter)
        self.edit.textChanged.connect(self._changed)
        self._changed(self.edit.text(), emit=False)

    def set_text(self, text: str) -> None:
        self.edit.blockSignals(True)
        self.edit.setText(text)
        self.edit.blockSignals(False)
        self._changed(text, emit=False)

    def _changed(self, text: str, emit: bool = True) -> None:
        self.counter.setText(f"{len(text)}/{LABEL_CHARS}")
        ascii_text = transliterate(text)
        self.edit.setToolTip(f"Na ekranie: {ascii_text}" if ascii_text != text else "")
        if emit:
            self.changed.emit(text)


class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = "#3c4a5c"
        self.clicked.connect(self._pick)
        self.setFixedWidth(90)
        self._refresh()

    def set_color(self, color: str) -> None:
        self._color = color
        self._refresh()

    def _refresh(self) -> None:
        self.setText(self._color)
        text = "#000" if QColor(self._color).lightness() > 140 else "#fff"
        self.setStyleSheet(
            f"background:{self._color}; color:{text}; border-radius:4px; padding:4px;"
        )

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Kolor klawisza")
        if color.isValid():
            self._color = color.name()
            self._refresh()
            self.changed.emit(self._color)


class KeyEditor(QWidget):
    """Etykieta, kolor i akcje gestów tap / hold / double_tap jednego klawisza."""

    changed = Signal()

    def __init__(self, context: EditorContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.binding: KeyBinding | None = None
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 15pt; font-weight: 600;")
        self.label = LabelEdit()
        self.color = ColorButton()
        self.label.changed.connect(self._label_changed)
        self.color.changed.connect(self._color_changed)

        form = QFormLayout()
        form.addRow("Etykieta:", self.label)
        form.addRow("Kolor:", self.color)

        self.tabs = QTabWidget()
        self.editors: dict[str, ActionEditor] = {}
        for gesture, title in GESTURE_TABS:
            editor = ActionEditor(context)
            editor.changed.connect(lambda g=gesture: self._action_changed(g))
            self.editors[gesture] = editor
            self.tabs.addTab(editor, title)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addLayout(form)
        layout.addWidget(self.tabs, 1)

    def bind(self, key: int, binding: KeyBinding) -> None:
        self.binding = binding
        self.title.setText(f"Klawisz K{key}" if key != ENCODER_KEY else "Przycisk pokrętła")
        self.label.set_text(binding.label)
        self.color.set_color(binding.color)
        for gesture, editor in self.editors.items():
            editor.set_action(binding.action_for(gesture))
        self._update_tab_titles()

    def _update_tab_titles(self) -> None:
        if self.binding is None:
            return
        for i, (gesture, title) in enumerate(GESTURE_TABS):
            mark = " ●" if self.binding.action_for(gesture) else ""
            self.tabs.setTabText(i, title + mark)

    def _label_changed(self, text: str) -> None:
        if self.binding is not None:
            self.binding.label = text
            self.changed.emit()

    def _color_changed(self, color: str) -> None:
        if self.binding is not None:
            self.binding.color = color
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

    def __init__(self, context: EditorContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.profile: Profile | None = None
        title = QLabel("Pokrętło")
        title.setStyleSheet("font-size: 15pt; font-weight: 600;")

        presets = QGroupBox("Szybkie presety")
        self.preset_combo = QComboBox()
        for key, label in PRESETS:
            self.preset_combo.addItem(label, key)
        self.preset_target = QComboBox()
        self.preset_target.addItem("Obrót bez wciśnięcia", "")
        self.preset_target.addItem("Obrót z wciśniętym przyciskiem", "press_")
        self.process_combo = QComboBox()
        self.process_combo.setEditable(True)
        self.process_combo.setPlaceholderText("proces, np. spotify.exe")
        apply = QPushButton("Zastosuj")
        apply.clicked.connect(self._apply_preset)
        self.preset_combo.currentIndexChanged.connect(self._preset_changed)
        row = QHBoxLayout(presets)
        row.addWidget(self.preset_combo, 2)
        row.addWidget(self.process_combo, 2)
        row.addWidget(self.preset_target, 2)
        row.addWidget(apply)
        self._preset_changed()

        self.tabs = QTabWidget()
        self.editors: dict[str, ActionEditor] = {}
        for gesture, label in ENCODER_TABS:
            editor = ActionEditor(context)
            editor.changed.connect(lambda g=gesture: self._action_changed(g))
            self.editors[gesture] = editor
            self.tabs.addTab(editor, label)

        self.button_editor = KeyEditor(context)
        self.button_editor.title.hide()
        self.button_editor.changed.connect(self.changed)
        self.tabs.addTab(self.button_editor, "Przycisk")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
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
        for i, (gesture, label) in enumerate(ENCODER_TABS):
            mark = " ●" if self.profile.encoder.action_for(gesture) else ""
            self.tabs.setTabText(i, label + mark)

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
        title = QLabel("Profil")
        title.setStyleSheet("font-size: 15pt; font-weight: 600;")
        self.name = QLineEdit()
        self.name.editingFinished.connect(self._rename)
        self.default = QCheckBox("Profil domyślny (start aplikacji)")
        self.default.toggled.connect(self._default_toggled)
        self._is_default_cb: Callable[[Profile], bool] = lambda p: False
        self._set_default_cb: Callable[[Profile], None] = lambda p: None

        group = QGroupBox("Automatyczne przełączanie – gdy aktywne jest okno procesu:")
        self.processes = QListWidget()
        self.add_combo = QComboBox()
        self.add_combo.setEditable(True)
        self.add_combo.setPlaceholderText("np. obs64.exe")
        refresh = QPushButton("↻")
        refresh.setToolTip("Odśwież listę uruchomionych procesów")
        refresh.setFixedWidth(32)
        refresh.clicked.connect(self._refresh_running)
        add = QPushButton("Dodaj")
        add.clicked.connect(self._add_process)
        remove = QPushButton("Usuń")
        remove.clicked.connect(self._remove_process)
        row = QHBoxLayout()
        row.addWidget(self.add_combo, 1)
        row.addWidget(refresh)
        row.addWidget(add)
        row.addWidget(remove)
        g = QVBoxLayout(group)
        g.addWidget(self.processes)
        g.addLayout(row)

        hint = QLabel(
            "Kliknij klawisz lub pokrętło na podglądzie, aby edytować akcje. "
            "Fizyczne naciśnięcia podświetlają elementy na żywo."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")

        form = QFormLayout()
        form.addRow("Nazwa:", self.name)
        form.addRow("", self.default)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(group, 1)
        layout.addWidget(hint)
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
