"""Edytor akcji: wybór typu i formularz generowany z pól modelu pydantic.

Nowy typ akcji zarejestrowany w core/actions automatycznie dostaje tu formularz.
Podpowiedzi widżetów: json_schema_extra={"widget": "exe" | "folder" | "path" | "hotkey" |
"multiline" | "process" | "profile" | "macro"}, etykiety wartości Literal: {"labels": {...}}.
"""

from __future__ import annotations

import typing
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.actions import ACTION_TYPES, ActionBase, MacroStep, format_hotkey, parse_hotkey
from . import theme
from .i18n import action_summary, tr
from .widgets import Switch, combo, label, styled

NONE_LABEL = "(brak akcji)"


@dataclass
class EditorContext:
    """Dane potrzebne formularzom (listy profili i procesów)."""

    profile_names: Callable[[], list[str]] = lambda: []
    audio_processes: Callable[[], list[str]] = lambda: []
    running_processes: Callable[[], list[str]] = lambda: []
    test_action: Callable[[ActionBase], None] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- nagrywanie skrótu

_QT_KEY_NAMES: dict[int, str] = {
    Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter", Qt.Key.Key_Escape: "esc",
    Qt.Key.Key_Tab: "tab", Qt.Key.Key_Backtab: "tab", Qt.Key.Key_Space: "space",
    Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Delete: "delete", Qt.Key.Key_Insert: "insert",
    Qt.Key.Key_Home: "home", Qt.Key.Key_End: "end", Qt.Key.Key_PageUp: "pageup",
    Qt.Key.Key_PageDown: "pagedown", Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
    Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right", Qt.Key.Key_CapsLock: "capslock",
    Qt.Key.Key_Print: "printscreen", Qt.Key.Key_ScrollLock: "scrolllock",
    Qt.Key.Key_Pause: "pause", Qt.Key.Key_Menu: "menu", Qt.Key.Key_NumLock: "numlock",
    Qt.Key.Key_Plus: "plus", Qt.Key.Key_Minus: "-", Qt.Key.Key_Equal: "=",
    Qt.Key.Key_BracketLeft: "[", Qt.Key.Key_BracketRight: "]", Qt.Key.Key_Backslash: "\\",
    Qt.Key.Key_Semicolon: ";", Qt.Key.Key_Apostrophe: "'", Qt.Key.Key_Comma: ",",
    Qt.Key.Key_Period: ".", Qt.Key.Key_Slash: "/", Qt.Key.Key_QuoteLeft: "`",
    Qt.Key.Key_MediaPlay: "media_play_pause", Qt.Key.Key_MediaTogglePlayPause: "media_play_pause",
    Qt.Key.Key_MediaNext: "media_next", Qt.Key.Key_MediaPrevious: "media_prev",
}  # fmt: skip
_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr,
}


def qt_key_name(key: int) -> str | None:
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(ord("a") + key - Qt.Key.Key_A)
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(ord("0") + key - Qt.Key.Key_0)
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        return f"f{key - Qt.Key.Key_F1 + 1}"
    return _QT_KEY_NAMES.get(key)


def modifiers_of(event: QKeyEvent) -> list[str]:
    mods = event.modifiers()
    names = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        names.append("ctrl")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        names.append("shift")
    if mods & Qt.KeyboardModifier.AltModifier:
        names.append("alt")
    if mods & Qt.KeyboardModifier.MetaModifier:
        names.append("win")
    return names


class HotkeyEdit(QWidget):
    """Pole skrótu z przyciskiem „Nagraj skrót”."""

    changed = Signal(str)

    def __init__(self, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit(value)
        self.edit.setPlaceholderText(tr("np. ctrl+shift+c, win+e, f13"))
        self.button = QPushButton(tr("Nagraj skrót"))
        self.button.setCheckable(True)
        styled(self.button, record=True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)
        self.button.toggled.connect(self._toggle)
        self.edit.textChanged.connect(self.changed)
        self.edit.installEventFilter(self)
        self._before = value

    def value(self) -> str:
        return self.edit.text().strip()

    def _toggle(self, recording: bool) -> None:
        if recording:
            self._before = self.edit.text()
            self.edit.setText("")
            self.edit.setPlaceholderText(tr("Naciśnij kombinację klawiszy…"))
            self.edit.setFocus()
            self.button.setText(tr("Anuluj"))
        else:
            self.button.setText(tr("Nagraj skrót"))
            self.edit.setPlaceholderText(tr("np. ctrl+shift+c, win+e, f13"))
            if not self.edit.text():
                self.edit.setText(self._before)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not self.button.isChecked() or obj is not self.edit:
            return False
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            mods = modifiers_of(event)
            key = event.key()
            if key in _MODIFIER_KEYS:
                self.edit.setText("+".join(mods) + "+…")
                return True
            name = qt_key_name(key)
            if name is None:
                return True
            keys = [*mods, name]
            self.edit.setText(format_hotkey(keys).lower())
            self.button.setChecked(False)
            return True
        return False


# --------------------------------------------------------------------------- pola ścieżek


class PathEdit(QWidget):
    changed = Signal(str)

    def __init__(self, value: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.edit = QLineEdit(value)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        if kind in ("exe", "path"):
            b = QPushButton(tr("Plik…"))
            b.clicked.connect(self._pick_file)
            layout.addWidget(b)
        if kind in ("folder", "path"):
            b = QPushButton(tr("Folder…"))
            b.clicked.connect(self._pick_folder)
            layout.addWidget(b)
        self.edit.textChanged.connect(self.changed)

    def value(self) -> str:
        return self.edit.text().strip()

    def _pick_file(self) -> None:
        filt = (
            tr("Programy (*.exe *.bat *.cmd *.lnk);;Wszystkie pliki (*)")
            if self.kind == "exe"
            else tr("Wszystkie pliki (*)")
        )
        path, _ = QFileDialog.getOpenFileName(self, tr("Wybierz plik"), self.edit.text(), filt)
        if path:
            self.edit.setText(path.replace("/", "\\"))

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("Wybierz folder"), self.edit.text())
        if path:
            self.edit.setText(path.replace("/", "\\"))


# --------------------------------------------------------------------------- makra


class MacroEditor(QWidget):
    changed = Signal()

    def __init__(
        self, steps: list[MacroStep], context: EditorContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.steps = [MacroStep.model_validate(s.model_dump(mode="json")) for s in steps]
        self.list = QListWidget()
        self.list.setObjectName("boxed")
        self.list.setMinimumHeight(110)
        self.list.itemDoubleClicked.connect(lambda _: self._edit())
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        for text, slot in (
            ("Dodaj", self._add),
            ("Edytuj", self._edit),
            ("Usuń", self._remove),
            ("W górę", lambda: self._move(-1)),
            ("W dół", lambda: self._move(1)),
        ):
            b = QPushButton(tr(text))
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list, 1)
        layout.addLayout(buttons)
        self._refresh()

    def _refresh(self, select: int | None = None) -> None:
        self.list.clear()
        for i, step in enumerate(self.steps, 1):
            delay = f"  (+{step.delay_ms} ms)" if step.delay_ms else ""
            self.list.addItem(QListWidgetItem(f"{i}. {action_summary(step.action)}{delay}"))
        if select is not None and 0 <= select < len(self.steps):
            self.list.setCurrentRow(select)

    def _dialog(self, step: MacroStep | None) -> MacroStep | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Krok makra"))
        editor = ActionEditor(self.context, allow_none=False)
        editor.set_action(step.action if step else ACTION_TYPES["hotkey"](type="hotkey"))
        delay = QSpinBox()
        delay.setRange(0, 60000)
        delay.setSuffix(" ms")
        delay.setValue(step.delay_ms if step else 0)
        form = QFormLayout()
        form.addRow(tr("Opóźnienie po kroku:"), delay)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(dialog.accept)
        box.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addWidget(editor)
        layout.addLayout(form)
        layout.addWidget(box)
        dialog.resize(520, 380)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        action = editor.action()
        if action is None:
            return None
        return MacroStep(action=action, delay_ms=delay.value())

    def _add(self) -> None:
        step = self._dialog(None)
        if step is not None:
            self.steps.append(step)
            self._refresh(len(self.steps) - 1)
            self.changed.emit()

    def _edit(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        step = self._dialog(self.steps[row])
        if step is not None:
            self.steps[row] = step
            self._refresh(row)
            self.changed.emit()

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            del self.steps[row]
            self._refresh(min(row, len(self.steps) - 1))
            self.changed.emit()

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < len(self.steps):
            return
        self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
        self._refresh(target)
        self.changed.emit()

    def value(self) -> list[dict[str, Any]]:
        return [s.model_dump(mode="json") for s in self.steps]


# --------------------------------------------------------------------------- edytor akcji


def _literal_values(annotation: Any) -> tuple[Any, ...] | None:
    if typing.get_origin(annotation) is typing.Literal:
        return typing.get_args(annotation)
    return None


def _bounds(info: Any) -> tuple[float | None, float | None]:
    lo = hi = None
    for meta in info.metadata:
        lo = getattr(meta, "ge", lo) if getattr(meta, "ge", None) is not None else lo
        hi = getattr(meta, "le", hi) if getattr(meta, "le", None) is not None else hi
    return lo, hi


class ActionEditor(QWidget):
    """Wybór typu akcji + formularz parametrów + „Testuj”."""

    changed = Signal()

    def __init__(
        self, context: EditorContext, allow_none: bool = True, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.allow_none = allow_none
        self._action: ActionBase | None = None
        self._getters: dict[str, Callable[[], Any]] = {}
        self._loading = False

        self.type_combo = combo()
        if allow_none:
            self.type_combo.addItem(tr(NONE_LABEL), None)
        for name, cls in ACTION_TYPES.items():
            self.type_combo.addItem(tr(cls.label), name)
        self.type_combo.currentIndexChanged.connect(self._type_changed)

        self.test_button = QPushButton(tr("Testuj"))
        self.test_button.setIcon(theme.icon("play"))
        self.test_button.setToolTip(tr("Wykonaj akcję teraz"))
        self.test_button.clicked.connect(self._test)
        self.test_button.setVisible(context.test_action is not None)

        self.summary = label("", "muted")
        bottom = QHBoxLayout()
        bottom.addWidget(self.summary, 1)
        bottom.addWidget(self.test_button)

        self.description = label("", "hint", wrap=True)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 4, 0, 0)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.form.setVerticalSpacing(6)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.error = label("", "error", wrap=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(label(tr("Typ akcji"), "lbl"))
        layout.addWidget(self.type_combo)
        layout.addWidget(self.description)
        layout.addWidget(self.form_host)
        layout.addWidget(self.error)
        layout.addLayout(bottom)
        layout.addStretch(1)
        self.set_action(None)

    # ------------------------------------------------------------------ API

    def set_action(self, action: ActionBase | None) -> None:
        self._loading = True
        try:
            self._action = action
            kind = action.type if action is not None else None
            index = self.type_combo.findData(kind)
            if index < 0:
                if action is not None:  # nieznany typ – pokaż jako tekst
                    self.type_combo.addItem(f"{action.type} ({tr('nieznany')})", action.type)
                    index = self.type_combo.count() - 1
                else:
                    index = 0
            self.type_combo.setCurrentIndex(index)
            self._build_form()
        finally:
            self._loading = False

    def action(self) -> ActionBase | None:
        return self._action

    # ------------------------------------------------------------------ wewnętrzne

    def _type_changed(self) -> None:
        if self._loading:
            return
        kind = self.type_combo.currentData()
        if kind is None:
            self._action = None
        elif kind in ACTION_TYPES:
            self._action = ACTION_TYPES[kind].model_validate({"type": kind})
        self._loading = True
        try:
            self._build_form()
        finally:
            self._loading = False
        self.changed.emit()

    def _clear_form(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self._getters.clear()

    def _build_form(self) -> None:
        self._clear_form()
        self.error.clear()
        action = self._action
        if action is None or action.type not in ACTION_TYPES:
            self.description.setText("")
            self.description.setVisible(False)
            self.summary.setText("")
            self.test_button.setEnabled(False)
            return
        cls = type(action)
        self.description.setText(tr(cls.description))
        self.description.setVisible(bool(cls.description))
        self.summary.setText(action_summary(action))
        self.test_button.setEnabled(True)
        for name, info in cls.model_fields.items():
            if name == "type":
                continue
            widget, getter = self._make_widget(name, info, getattr(action, name))
            self._getters[name] = getter
            if isinstance(widget, Switch):
                self.form.addRow(widget)
            else:
                self.form.addRow(label(tr(info.title or name), "lbl"), widget)

    def _make_widget(self, name: str, info: Any, value: Any) -> tuple[QWidget, Callable[[], Any]]:
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        kind = extra.get("widget")
        annotation = info.annotation
        literal = _literal_values(annotation)

        if kind in ("exe", "folder", "path"):
            w = PathEdit(value or "", kind)
            w.changed.connect(self._field_changed)
            return w, w.value
        if kind == "hotkey":
            h = HotkeyEdit(value or "")
            h.changed.connect(self._field_changed)
            return h, h.value
        if kind == "multiline":
            t = QPlainTextEdit(value or "")
            t.setFixedHeight(70)
            t.textChanged.connect(self._field_changed)
            return t, t.toPlainText
        if kind in ("process", "profile"):
            c = combo()
            c.setEditable(kind == "process")
            c.setMinimumContentsLength(12)
            items = (
                self.context.profile_names()
                if kind == "profile"
                else sorted(
                    set(self.context.audio_processes()) | set(self.context.running_processes()),
                    key=str.lower,
                )
            )
            c.addItems(items)
            if value and c.findText(value) < 0:
                c.addItem(value)
            c.setCurrentText(value or "")
            c.currentTextChanged.connect(self._field_changed)
            return c, lambda: c.currentText().strip()
        if kind == "macro":
            m = MacroEditor(value or [], self.context)
            m.changed.connect(self._field_changed)
            return m, m.value
        if literal is not None:
            labels = extra.get("labels", {})
            c = combo()
            for option in literal:
                c.addItem(tr(str(labels.get(option, option))), option)
            c.setCurrentIndex(max(0, c.findData(value)))
            c.currentIndexChanged.connect(self._field_changed)
            return c, c.currentData
        if annotation is bool:
            b = Switch(tr(info.title or name))
            b.setChecked(bool(value))
            b.toggled.connect(self._field_changed)
            return b, b.isChecked
        if annotation is int:
            lo, hi = _bounds(info)
            s = QSpinBox()
            s.setRange(
                int(lo if lo is not None else -1_000_000), int(hi if hi is not None else 1_000_000)
            )
            s.setValue(int(value or 0))
            s.valueChanged.connect(self._field_changed)
            return s, s.value
        if annotation is float:
            lo, hi = _bounds(info)
            d = QDoubleSpinBox()
            d.setDecimals(1)
            d.setRange(float(lo if lo is not None else 0), float(hi if hi is not None else 1e6))
            d.setValue(float(value or 0))
            d.valueChanged.connect(self._field_changed)
            return d, d.value
        e = QLineEdit("" if value is None else str(value))
        e.textChanged.connect(self._field_changed)
        return e, lambda: e.text()

    def _field_changed(self, *_: Any) -> None:
        if self._loading or self._action is None:
            return
        cls = type(self._action)
        data = {"type": self._action.type}
        for name, getter in self._getters.items():
            data[name] = getter()
        try:
            self._action = cls.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            field_name = ".".join(str(x) for x in first.get("loc", ()))
            self.error.setText(f"{field_name}: {first.get('msg', '')}")
            return
        self.error.clear()
        self.summary.setText(action_summary(self._action))
        self.changed.emit()

    def _test(self) -> None:
        if self._action is not None and self.context.test_action is not None:
            self.context.test_action(self._action)


def hotkey_is_valid(text: str) -> bool:
    try:
        parse_hotkey(text)
        return True
    except ValueError:
        return False
