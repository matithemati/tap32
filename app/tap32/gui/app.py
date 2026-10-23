"""Uruchomienie aplikacji GUI: jedna instancja, zasobnik, kontroler, symulator."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import APP_NAME, __version__
from ..core.config import ConfigStore, default_config_dir
from ..core.engine import Controller
from ..core.logbuffer import setup_logging
from ..core.simulator import SimulatedDevice, SimulatorTransport
from ..core.transport import SerialTransport, Transport
from ..platform import create_platform
from .bridge import QtBridge
from .icons import app_icon
from .main_window import MainWindow
from .simulator_window import SimulatorWindow
from .tray import TrayIcon

log = logging.getLogger("tap32.gui")

SERVER_NAME = f"tap32-single-instance-{os.environ.get('USERNAME', 'user')}"


def notify_running_instance() -> bool:
    """Jeśli Tap32 już działa – poproś go o pokazanie okna i zwróć True."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(300):
        socket.write(b"show\n")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def dark_palette() -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: "#1e2227",
        QPalette.ColorRole.WindowText: "#e6e6e6",
        QPalette.ColorRole.Base: "#15181c",
        QPalette.ColorRole.AlternateBase: "#22262c",
        QPalette.ColorRole.ToolTipBase: "#2b3036",
        QPalette.ColorRole.ToolTipText: "#e6e6e6",
        QPalette.ColorRole.Text: "#e6e6e6",
        QPalette.ColorRole.Button: "#2b3036",
        QPalette.ColorRole.ButtonText: "#e6e6e6",
        QPalette.ColorRole.BrightText: "#ff5252",
        QPalette.ColorRole.Highlight: "#2f81c4",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: "#4fc3f7",
        QPalette.ColorRole.Mid: "#8a929c",
        QPalette.ColorRole.PlaceholderText: "#7c848e",
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#6c737c"))
    return p


def apply_theme(app: QApplication, theme: str) -> None:
    """Motyw jasny/ciemny; „system” – według ustawień Windows."""
    app.setStyle("Fusion")
    hints = app.styleHints()
    if theme == "system":
        if hasattr(hints, "unsetColorScheme"):
            hints.unsetColorScheme()
        dark = hints.colorScheme() == Qt.ColorScheme.Dark
    else:
        dark = theme == "dark"
        if hasattr(hints, "setColorScheme"):
            hints.setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
    app.setPalette(dark_palette() if dark else app.style().standardPalette())


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{exe}" -m tap32 --minimized'


def run(
    simulate: bool = False,
    minimized: bool = False,
    config_path: Path | None = None,
    verbose: bool = False,
    board: str = "kb2040",
) -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(__version__)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    if notify_running_instance():
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)

    config_dir = config_path.parent if config_path else default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    log_buffer = setup_logging(str(config_dir / "tap32.log"), verbose)
    log.info("Tap32 %s – start%s", __version__, " (symulator)" if simulate else "")

    store = ConfigStore(config_path)
    config = store.load()
    if not store.path.exists():
        store.save(config)  # pierwsze uruchomienie – zapisz profile domyślne
    apply_theme(app, config.settings.app.theme)
    app.styleHints().colorSchemeChanged.connect(
        lambda _: apply_theme(app, "system") if config.settings.app.theme == "system" else None
    )
    platform = create_platform()

    device: SimulatedDevice | None = None
    mirror = SimulatedDevice()  # lustro ekranu dla prawdziwego urządzenia
    transport: Transport
    if simulate:
        device = SimulatedDevice(board=board)
        transport = SimulatorTransport(device)
    else:
        transport = SerialTransport(config.settings.device.port, __version__)
        transport.on_sent = mirror.handle

    controller = Controller(config, transport, platform, store=store)
    bridge = QtBridge()
    controller.add_listener(bridge)
    log_buffer.add_listener(bridge.on_log)

    def screen() -> object:
        if device is not None:
            return device.screen()
        if not transport.connected:
            from ..core.simulator import Screen

            return Screen(kind="offline")
        return mirror.screen()

    tray = TrayIcon()

    def apply_app_settings() -> None:
        settings = config.settings.app
        apply_theme(app, settings.theme)
        try:
            if platform.get_autostart() != settings.autostart:
                platform.set_autostart(settings.autostart, autostart_command())
        except OSError as exc:
            log.error("Nie udało się zmienić autostartu: %s", exc)
        tray.set_profiles(config.profile_names(), controller.profiles.active.name)

    window = MainWindow(controller, bridge, screen, apply_app_settings, log_buffer.snapshot())  # type: ignore[arg-type]

    def update_tray_status(connected: bool, info: object, port: object) -> None:
        if connected:
            tray.set_status("connected", f"Tap32 – połączono ({port})")
        else:
            tray.set_status("disconnected", "Tap32 – rozłączono")

    def set_paused(paused: bool) -> None:
        controller.paused = paused
        tray.set_paused(paused)
        window.set_paused(paused)
        log.info("Akcje %s", "wstrzymane" if paused else "wznowione")

    def quit_app() -> None:
        window.quitting = True
        window.close()
        app.quit()

    bridge.connectionChanged.connect(update_tray_status)
    bridge.profileChanged.connect(
        lambda profile, reason: tray.set_profiles(
            config.profile_names(), controller.profiles.active.name
        )
    )
    tray.openRequested.connect(window.show_and_raise)
    tray.quitRequested.connect(quit_app)
    tray.pauseToggled.connect(set_paused)
    tray.profileRequested.connect(
        lambda name: controller.call_soon(lambda: controller.profiles.set_active(name))
    )
    tray.set_profiles(config.profile_names(), controller.profiles.active.name)
    tray.show()

    def on_new_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is not None:

            def on_ready() -> None:
                connection.readAll()
                window.show_and_raise()

            connection.readyRead.connect(on_ready)

    server.newConnection.connect(on_new_connection)

    if device is not None:
        sim_window = SimulatorWindow(device)
        sim_window.show()

    if not (minimized or config.settings.app.start_minimized) or not tray_available():
        window.show()

    controller.start()
    app.aboutToQuit.connect(controller.stop)
    try:
        return app.exec()
    except Exception as exc:  # pragma: no cover
        QMessageBox.critical(None, APP_NAME, str(exc))
        return 1


def tray_available() -> bool:
    from PySide6.QtWidgets import QSystemTrayIcon

    return QSystemTrayIcon.isSystemTrayAvailable()
