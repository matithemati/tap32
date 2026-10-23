"""Ikona w zasobniku systemowym."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from .i18n import tr
from .icons import app_icon


class TrayIcon(QSystemTrayIcon):
    openRequested = Signal()
    quitRequested = Signal()
    profileRequested = Signal(str)
    pauseToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(app_icon("disconnected"), parent)
        self.setToolTip(tr("Tap32 – rozłączono"))
        self.menu = QMenu()
        self.open_action = self.menu.addAction("")
        self.open_action.triggered.connect(self.openRequested)
        self.menu.setDefaultAction(self.open_action)
        self.profiles_menu = self.menu.addMenu("")
        self._profile_group = QActionGroup(self)
        self._profile_group.setExclusive(True)
        self.pause_action = self.menu.addAction("")
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.pauseToggled)
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("")
        self.quit_action.triggered.connect(self.quitRequested)
        self.setContextMenu(self.menu)
        self.activated.connect(self._activated)
        self._status = "disconnected"
        self._paused = False
        self.retranslate()

    def retranslate(self) -> None:
        self.open_action.setText(tr("Otwórz Tap32"))
        self.profiles_menu.setTitle(tr("Profil"))
        self.pause_action.setText(tr("Wstrzymaj akcje"))
        self.quit_action.setText(tr("Zakończ"))

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.openRequested.emit()

    def set_profiles(self, names: list[str], active: str) -> None:
        self.profiles_menu.clear()
        for action in self._profile_group.actions():
            self._profile_group.removeAction(action)
        for name in names:
            action = QAction(name, self.profiles_menu)
            action.setCheckable(True)
            action.setChecked(name == active)
            action.triggered.connect(lambda _=False, n=name: self.profileRequested.emit(n))
            self._profile_group.addAction(action)
            self.profiles_menu.addAction(action)

    def set_status(self, status: str, tooltip: str) -> None:
        self._status = status
        self.setToolTip(tooltip)
        self._refresh_icon()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.pause_action.blockSignals(True)
        self.pause_action.setChecked(paused)
        self.pause_action.blockSignals(False)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        self.setIcon(app_icon("paused" if self._paused else self._status))
