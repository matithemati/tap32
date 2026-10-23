"""Symulator urządzenia Tap32 – ta sama logika protokołu co firmware, bez sprzętu.

`SimulatedDevice` jest czysty (bez Qt); okno symulatora (gui/simulator_window.py) tylko go
wyświetla i przekazuje kliknięcia. `SimulatorTransport` łączy go z kontrolerem w procesie,
z pełnym kodowaniem/dekodowaniem JSON (testuje też protokół).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from . import protocol
from .protocol import ProtocolError
from .transport import ConnectionState, Transport

log = logging.getLogger("tap32.simulator")

FW_VERSION = "1.0.0-sim"


@dataclass(frozen=True)
class Screen:
    """Co jest na ekranie OLED (do narysowania przez GUI)."""

    kind: str  # splash | offline | idle | profile | grid | text | bar | flash | test | off
    title: str = ""
    labels: tuple[str, ...] = ()
    line1: str = ""
    line2: str = ""
    value: int = 0
    key: int | None = None
    online: bool = False
    test_keys: tuple[bool, ...] = ()
    test_steps: int = 0
    flip: bool = False
    brightness: int = 128


@dataclass
class SimulatedDevice:
    board: str = "kb2040"
    clock: Callable[[], float] = time.monotonic
    emit: Callable[[dict[str, Any]], None] = lambda message: None
    settings: dict[str, Any] = field(
        default_factory=lambda: {
            "brightness": 128,
            "screensaver_s": 300,
            "flip": False,
            "enc_reverse": False,
            "enc_pulses": 4,
            "debounce_ms": 8,
            "oled_addr": 0x3C,
        }
    )
    fallback: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "10": {"media": "mute"},
            "enc_cw": {"media": "vol_up"},
            "enc_ccw": {"media": "vol_down"},
        }
    )

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self._start = self.clock()
        self._last_rx: float | None = None
        self._base = Screen(kind="idle")
        self._overlay: Screen | None = None
        self._overlay_until = 0.0
        self._flash: Screen | None = None
        self._flash_until = 0.0
        self._last_activity = self._start
        self._pressed = [False] * protocol.KEY_COUNT
        self._test_mode = False
        self._test_steps = 0
        self.debug = False
        self.hid_log: list[str] = []  # co zostałoby wysłane przez HID w trybie offline

    # ------------------------------------------------------------------ czas i stan

    def _ms(self) -> int:
        return int((self.clock() - self._start) * 1000)

    @property
    def online(self) -> bool:
        with self._lock:
            return (
                self._last_rx is not None
                and self.clock() - self._last_rx < protocol.HEARTBEAT_TIMEOUT_S
            )

    def screen(self) -> Screen:
        """Aktualny obraz ekranu (uwzględnia wygaszacz, nakładki i tryb offline)."""
        with self._lock:
            now = self.clock()
            flip = bool(self.settings["flip"])
            brightness = int(self.settings["brightness"])
            if now - self._start < 1.5:
                return Screen(kind="splash", flip=flip, brightness=brightness)
            saver = int(self.settings["screensaver_s"])
            if saver and not self._test_mode and now - self._last_activity >= saver:
                return Screen(kind="off")
            if self._test_mode:
                return Screen(
                    kind="test",
                    test_keys=tuple(self._pressed),
                    test_steps=self._test_steps,
                    flip=flip,
                    brightness=brightness,
                )
            online = self.online
            if self._flash is not None and now < self._flash_until:
                return replace(self._flash, online=online, flip=flip, brightness=brightness)
            if not online:
                return Screen(kind="offline", flip=flip, brightness=brightness)
            if self._overlay is not None and now < self._overlay_until:
                return replace(self._overlay, online=online, flip=flip, brightness=brightness)
            return replace(self._base, online=online, flip=flip, brightness=brightness)

    # ------------------------------------------------------------------ wejścia (UI)

    def press(self, key: int) -> None:
        self._key(key, True)

    def release(self, key: int) -> None:
        self._key(key, False)

    def _key(self, key: int, down: bool) -> None:
        with self._lock:
            if self._pressed[key - 1] == down:
                return
            self._pressed[key - 1] = down
            self._last_activity = self.clock()
            offline = not self.online
        self.emit({"type": "key", "key": key, "action": "down" if down else "up", "t": self._ms()})
        if offline and down:
            self._hid(str(key))

    def rotate(self, steps: int) -> None:
        if steps == 0:
            return
        with self._lock:
            if self.settings["enc_reverse"]:
                steps = -steps
            self._last_activity = self.clock()
            self._test_steps += steps
            offline = not self.online
        self.emit({"type": "enc", "steps": steps, "t": self._ms()})
        if offline:
            for _ in range(abs(steps)):
                self._hid("enc_cw" if steps > 0 else "enc_ccw")

    def _hid(self, slot: str) -> None:
        binding = self.fallback.get(slot)
        if binding:
            self.hid_log.append(f"{slot}: {binding}")
            log.info("[symulator HID] %s → %s", slot, binding)

    # ------------------------------------------------------------------ protokół

    def handle_line(self, line: bytes) -> None:
        try:
            message = protocol.decode(line)
        except ProtocolError as exc:
            self.emit({"type": "error", "msg": str(exc)})
            return
        self.handle(message)

    def handle(self, message: dict[str, Any]) -> None:
        msg_id = message.get("id")
        has_id = isinstance(msg_id, int) and not isinstance(msg_id, bool)
        try:
            known = self._dispatch(message)
        except ProtocolError as exc:
            reply: dict[str, Any] = {"type": "error", "msg": str(exc)}
            if has_id:
                reply["id"] = msg_id
            self.emit(reply)
            return
        if known and has_id and message.get("type") != "reboot":
            self.emit({"type": "ack", "id": msg_id})

    def _hello(self) -> dict[str, Any]:
        return {
            "type": "hello",
            "device": "tap32",
            "fw": FW_VERSION,
            "board": self.board,
            "keys": protocol.KEY_COUNT,
            "encoder": True,
            "hid": True,
            "online": self.online,
            "oled": 0x3C,
            "i2c": [0x3C],
        }

    def _dispatch(self, message: dict[str, Any]) -> bool:
        kind = message["type"]
        with self._lock:
            self._last_rx = self.clock()
        if kind == "hello" or kind == "get_info":
            self.emit(self._hello())
        elif kind == "ping":
            pass
        elif kind == "display":
            self._display(message)
        elif kind == "flash":
            text = message.get("text")
            if not isinstance(text, str):
                raise ProtocolError("missing text")
            ms = int(message.get("ms", 1000))
            with self._lock:
                self._flash = Screen(kind="flash", line1=text[:21], key=message.get("key"))
                self._flash_until = self.clock() + ms / 1000
                self._last_activity = self.clock()
        elif kind == "settings":
            updates = {k: v for k, v in message.items() if k in protocol.SETTINGS_FIELDS}
            protocol.msg_settings(**updates)  # ta sama walidacja co firmware
            with self._lock:
                self.settings.update(updates)
        elif kind == "set_fallback":
            self._set_fallback(message)
        elif kind == "reboot":
            msg_id = message.get("id")
            if isinstance(msg_id, int):
                self.emit({"type": "ack", "id": msg_id})
            with self._lock:
                self._last_rx = None
                self._start = self.clock()
            self.emit(self._hello())
        elif kind == "test_mode":
            with self._lock:
                self._test_mode = bool(message.get("enable", True))
                self._test_steps = 0
            self.emit({"type": "test", "active": self._test_mode})
        elif kind == "debug":
            self.debug = bool(message.get("enable", True))
        else:
            return False
        return True

    def _display(self, message: dict[str, Any]) -> None:
        mode = message.get("mode")
        ms = int(message.get("ms", 0) or 0)
        if mode == "profile":
            screen = Screen(kind="profile", title=str(message.get("name", ""))[:21])
        elif mode == "grid":
            labels = message.get("labels", [])
            if not isinstance(labels, list) or len(labels) > 9:
                raise ProtocolError("labels must be an array")
            padded = [str(x or "")[:7] for x in labels] + [""] * (9 - len(labels))
            screen = Screen(
                kind="grid", title=str(message.get("title", ""))[:21], labels=tuple(padded)
            )
        elif mode == "text":
            screen = Screen(
                kind="text",
                line1=str(message.get("line1", ""))[:21],
                line2=str(message.get("line2", ""))[:21],
            )
        elif mode == "bar":
            value = max(0, min(100, int(message.get("value", 0))))
            screen = Screen(kind="bar", title=str(message.get("title", ""))[:21], value=value)
        else:
            raise ProtocolError("unknown display mode")
        with self._lock:
            if mode in ("text", "bar") and ms > 0:
                self._overlay = screen
                self._overlay_until = self.clock() + ms / 1000
            else:
                self._base = screen
                self._overlay = None

    def _set_fallback(self, message: dict[str, Any]) -> None:
        bindings = message.get("bindings")
        if bindings is None and "key" in message:
            bindings = [message]
        if not isinstance(bindings, list):
            if message.get("replace"):
                bindings = []
            else:
                raise ProtocolError("missing key or bindings")
        parsed: dict[str, dict[str, Any]] = {}
        for item in bindings:
            slot = str(item.get("key"))
            if slot not in {str(i) for i in range(1, 11)} | {"enc_cw", "enc_ccw"}:
                raise ProtocolError("unknown key")
            if item.get("media") and item.get("code"):
                raise ProtocolError("use either code or media")
            parsed[slot] = {k: v for k, v in item.items() if k in ("mods", "code", "media")}
        with self._lock:
            if message.get("replace"):
                self.fallback = {}
            self.fallback.update(parsed)


class SimulatorTransport(Transport):
    """Transport w procesie: kontroler ↔ SimulatedDevice (przez kodowanie JSON)."""

    def __init__(self, device: SimulatedDevice) -> None:
        super().__init__()
        self.device = device
        device.emit = self._from_device
        self._started = False

    def start(self) -> None:
        self._started = True
        # Jak prawdziwy transport: handshake hello.
        self._set_state(ConnectionState.CONNECTING)
        self.device.handle_line(protocol.encode(protocol.msg_hello("sim")))

    def stop(self) -> None:
        self._started = False
        self._set_state(ConnectionState.DISCONNECTED)

    def send(self, message: dict[str, Any]) -> bool:
        if not self._started:
            return False
        self.device.handle_line(protocol.encode(message))
        self._notify_sent(message)
        return True

    def _from_device(self, message: dict[str, Any]) -> None:
        data = protocol.decode(protocol.encode(message))
        if data["type"] == "hello" and self.state != ConnectionState.CONNECTED:
            info = protocol.parse_device_message(data)
            if isinstance(info, protocol.DeviceInfo):
                self._set_state(ConnectionState.CONNECTED, info, "symulator")
        self.on_message(data)
