"""Transport wiadomości: interfejs, port szeregowy (USB CDC) z automatycznym wykrywaniem."""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import Any

from . import protocol
from .protocol import DeviceInfo, ProtocolError

log = logging.getLogger("tap32.transport")

# VID płytek: Espressif (ESP32-S3 TinyUSB), Adafruit (KB2040), Seeed (wariant XIAO ESP32-S3
# ustawia własny VID 0x2886). Nazwa produktu USB „Tap32” ma pierwszeństwo.
KNOWN_VIDS = {0x303A: "Espressif", 0x239A: "Adafruit", 0x2886: "Seeed"}
PRODUCT_NAME = "Tap32"


class ConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


MessageCallback = Callable[[dict[str, Any]], None]
StateCallback = Callable[[ConnectionState, DeviceInfo | None, str | None], None]


class Transport(ABC):
    """Dwukierunkowy kanał wiadomości JSON. Callbacki mogą być wołane z innych wątków."""

    def __init__(self) -> None:
        self.on_message: MessageCallback = lambda message: None
        self.on_state: StateCallback = lambda state, info, port: None
        # Wywoływane po wysłaniu wiadomości (np. lustrzany podgląd ekranu w GUI)
        self.on_sent: MessageCallback = lambda message: None
        self.state = ConnectionState.DISCONNECTED
        self.device_info: DeviceInfo | None = None
        self.port_name: str | None = None

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def send(self, message: dict[str, Any]) -> bool: ...

    def _notify_sent(self, message: dict[str, Any]) -> None:
        try:
            self.on_sent(message)
        except Exception:
            log.exception("Błąd w obsłudze wysłanej wiadomości")

    @property
    def connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def _set_state(
        self, state: ConnectionState, info: DeviceInfo | None = None, port: str | None = None
    ) -> None:
        self.state = state
        self.device_info = info
        self.port_name = port
        try:
            self.on_state(state, info, port)
        except Exception:
            log.exception("Błąd w obsłudze zmiany stanu połączenia")


# --------------------------------------------------------------------------- wykrywanie portu


def _port_text(port: Any) -> str:
    parts = [getattr(port, attr, None) for attr in ("product", "manufacturer", "description")]
    return " ".join(p for p in parts if p)


def candidate_ports(ports: Iterable[Any] | None = None) -> list[str]:
    """Porty, na których może być Tap32 – najpierw po nazwie produktu, potem po VID."""
    if ports is None:
        from serial.tools import list_ports

        ports = list_ports.comports()
    by_name: list[str] = []
    by_vid: list[str] = []
    for port in ports:
        if PRODUCT_NAME.lower() in _port_text(port).lower():
            by_name.append(port.device)
        elif getattr(port, "vid", None) in KNOWN_VIDS:
            by_vid.append(port.device)
    return by_name + by_vid


def list_all_ports() -> list[tuple[str, str]]:
    from serial.tools import list_ports

    return [(p.device, p.description or p.device) for p in list_ports.comports()]


# --------------------------------------------------------------------------- port szeregowy


class SerialTransport(Transport):
    """USB CDC w osobnym wątku: wykrywa port, potwierdza `hello`, łączy się ponownie."""

    def __init__(
        self,
        port: str = "auto",
        app_version: str = "1.0.0",
        serial_factory: Callable[[], Any] | None = None,
        port_lister: Callable[[], list[str]] | None = None,
        hello_timeout: float = 1.5,
        retry_interval: float = 1.0,
    ) -> None:
        super().__init__()
        self.port = port
        self.app_version = app_version
        self._serial_factory = serial_factory
        self._port_lister = port_lister or candidate_ports
        self._hello_timeout = hello_timeout
        self._retry_interval = retry_interval
        self._serial: Any = None
        self._write_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="tap32-serial", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._close()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def set_port(self, port: str) -> None:
        """Zmiana portu (auto / COMx) – rozłącza i wykrywa ponownie."""
        if port != self.port:
            self.port = port
            self._close()

    def send(self, message: dict[str, Any]) -> bool:
        try:
            data = protocol.encode(message)
        except ProtocolError as exc:
            log.error("Nie wysłano wiadomości: %s", exc)
            return False
        with self._write_lock:
            ser = self._serial
            if ser is None:
                return False
            try:
                ser.write(data)
            except Exception as exc:
                log.warning("Błąd zapisu do portu: %s", exc)
            else:
                self._notify_sent(message)
                return True
        self._close()
        return False

    # ------------------------------------------------------------------ wątek

    def _open(self, port: str) -> Any:
        if self._serial_factory is not None:
            ser = self._serial_factory()
        else:
            import serial

            ser = serial.Serial()
        ser.port = port
        ser.baudrate = 115200
        ser.timeout = 0.1
        ser.write_timeout = 0.5
        # DTR=1 (urządzenie wie, że host słucha), RTS=0 – żadnej sekwencji resetu ESP32.
        ser.dtr = True
        ser.rts = False
        ser.open()
        return ser

    def _handshake(self, port: str) -> DeviceInfo | None:
        try:
            ser = self._open(port)
        except Exception as exc:
            log.debug("Nie można otworzyć %s: %s", port, exc)
            return None
        try:
            ser.reset_input_buffer()
            ser.write(protocol.encode(protocol.msg_hello(self.app_version)))
            deadline = time.monotonic() + self._hello_timeout
            while time.monotonic() < deadline and not self._stop.is_set():
                line = ser.readline()
                if not line:
                    continue
                try:
                    data = protocol.decode(line)
                    if data.get("type") == "hello":
                        info = protocol.parse_device_message(data)
                        if isinstance(info, DeviceInfo):
                            self._serial = ser
                            return info
                except ProtocolError:
                    continue
        except Exception as exc:
            log.debug("Handshake na %s nieudany: %s", port, exc)
        try:
            ser.close()
        except Exception:
            pass
        return None

    def _connect(self) -> bool:
        ports = [self.port] if self.port and self.port != "auto" else self._port_lister()
        if not ports:
            return False
        self._set_state(ConnectionState.CONNECTING)
        for port in ports:
            info = self._handshake(port)
            if info is not None:
                log.info("Połączono z Tap32 (%s, fw %s) na %s", info.board_name, info.fw, port)
                self._set_state(ConnectionState.CONNECTED, info, port)
                return True
        self._set_state(ConnectionState.DISCONNECTED)
        return False

    def _close(self) -> None:
        with self._write_lock:
            ser, self._serial = self._serial, None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._serial is None:
                if self.state == ConnectionState.CONNECTED:
                    log.info("Rozłączono z Tap32")
                    self._set_state(ConnectionState.DISCONNECTED)
                if not self._connect():
                    self._stop.wait(self._retry_interval)
                continue
            try:
                line = self._serial.readline()
            except Exception as exc:
                log.info("Utracono połączenie: %s", exc)
                self._close()
                continue
            if not line:
                continue
            try:
                message = protocol.decode(line)
            except ProtocolError as exc:
                log.debug("Odrzucono linię: %s", exc)
                continue
            try:
                self.on_message(message)
            except Exception:
                log.exception("Błąd obsługi wiadomości")
        self._close()
        if self.state != ConnectionState.DISCONNECTED:
            self._set_state(ConnectionState.DISCONNECTED)
