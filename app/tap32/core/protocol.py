"""Protokół Tap32 (JSON Lines) – kodowanie, dekodowanie i walidacja wiadomości.

Pełny opis: docs/PROTOCOL.md. Moduł nie zależy od transportu ani od GUI.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
MAX_LINE_LENGTH = 1024
PING_INTERVAL_S = 1.0
HEARTBEAT_TIMEOUT_S = 3.0

TITLE_CHARS = 21
LABEL_CHARS = 7
ENCODER_KEY = 10
KEY_COUNT = 10

BOARD_NAMES = {"kb2040": "KB2040", "xiao_esp32s3": "XIAO ESP32-S3"}

MEDIA_KEYS = ("play_pause", "next", "prev", "stop", "vol_up", "vol_down", "mute")
HID_MODIFIERS = ("ctrl", "shift", "alt", "win", "rctrl", "rshift", "ralt", "rwin")


class ProtocolError(ValueError):
    """Niepoprawna wiadomość."""


# --------------------------------------------------------------------------- kodowanie


def encode(message: dict[str, Any]) -> bytes:
    """Zamienia wiadomość na linię JSON zakończoną \\n (UTF-8)."""
    if "type" not in message:
        raise ProtocolError("message without type")
    line = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    data = (line + "\n").encode("utf-8")
    if len(data) > MAX_LINE_LENGTH:
        raise ProtocolError(f"message too long ({len(data)} bytes)")
    return data


def decode(line: bytes | str) -> dict[str, Any]:
    """Dekoduje jedną linię. Rzuca ProtocolError dla niepoprawnych danych."""
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("invalid utf-8") from exc
    line = line.strip()
    if not line:
        raise ProtocolError("empty line")
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid json: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ProtocolError("object expected")
    if not isinstance(data.get("type"), str):
        raise ProtocolError("missing type")
    return data


# --------------------------------------------------------------------------- transliteracja

_POLISH = str.maketrans(
    {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
        "–": "-", "—": "-", "…": "...", "„": '"', "”": '"', "“": '"', "’": "'", "‘": "'",
        "×": "x", "→": ">", "←": "<", "▶": ">", "⏸": "||", "⏭": ">>", "⏮": "<<",
    }
)  # fmt: skip


def transliterate(text: str) -> str:
    """Zamienia tekst na ASCII (czcionki OLED nie mają polskich znaków)."""
    text = text.translate(_POLISH)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if ord(c) < 128 and not unicodedata.combining(c))
    return "".join(c if c.isprintable() else " " for c in ascii_text)


def fit(text: str, max_chars: int) -> str:
    """Transliteracja + obcięcie do limitu znaków."""
    return transliterate(text)[:max_chars]


# --------------------------------------------------------------------------- PC → urządzenie


def msg_hello(app_version: str) -> dict[str, Any]:
    return {"type": "hello", "app": app_version}


def msg_ping() -> dict[str, Any]:
    return {"type": "ping"}


def msg_get_info() -> dict[str, Any]:
    return {"type": "get_info"}


def msg_display_profile(name: str) -> dict[str, Any]:
    return {"type": "display", "mode": "profile", "name": fit(name, TITLE_CHARS)}


def msg_display_grid(title: str, labels: list[str]) -> dict[str, Any]:
    padded = [fit(label, LABEL_CHARS) for label in labels[:9]]
    padded += [""] * (9 - len(padded))
    return {"type": "display", "mode": "grid", "title": fit(title, TITLE_CHARS), "labels": padded}


def msg_display_text(line1: str, line2: str = "", ms: int = 0) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "type": "display",
        "mode": "text",
        "line1": fit(line1, TITLE_CHARS),
        "line2": fit(line2, TITLE_CHARS),
    }
    if ms:
        msg["ms"] = int(ms)
    return msg


def msg_display_bar(title: str, value: float, ms: int = 1500) -> dict[str, Any]:
    clamped = max(0, min(100, round(value)))
    msg: dict[str, Any] = {
        "type": "display",
        "mode": "bar",
        "title": fit(title, TITLE_CHARS),
        "value": clamped,
    }
    if ms:
        msg["ms"] = int(ms)
    return msg


def msg_flash(text: str, key: int | None = None, ms: int = 1000) -> dict[str, Any]:
    msg: dict[str, Any] = {"type": "flash", "text": fit(text, TITLE_CHARS), "ms": int(ms)}
    if key is not None:
        msg["key"] = int(key)
    return msg


SETTINGS_FIELDS = {
    "brightness": (int, 0, 255),
    "screensaver_s": (int, 0, 65535),
    "flip": (bool, None, None),
    "enc_reverse": (bool, None, None),
    "enc_pulses": (int, 1, 8),
    "debounce_ms": (int, 1, 50),
    "oled_addr": (int, 0x08, 0x77),
}


def msg_settings(**values: Any) -> dict[str, Any]:
    """Wiadomość settings z walidacją zakresów (zgodnie z firmware)."""
    msg: dict[str, Any] = {"type": "settings"}
    for key, value in values.items():
        if key not in SETTINGS_FIELDS:
            raise ProtocolError(f"unknown setting {key}")
        kind, lo, hi = SETTINGS_FIELDS[key]
        if kind is bool:
            if not isinstance(value, bool):
                raise ProtocolError(f"{key}: bool expected")
        else:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ProtocolError(f"{key}: int expected")
            assert lo is not None and hi is not None
            if not lo <= value <= hi:
                raise ProtocolError(f"{key}: out of range {lo}..{hi}")
        msg[key] = value
    return msg


@dataclass(frozen=True)
class FallbackBinding:
    """Skrót HID trybu awaryjnego. slot: 1..10 albo 'enc_cw' / 'enc_ccw'."""

    slot: int | str
    mods: tuple[str, ...] = ()
    code: str | None = None
    media: str | None = None

    def to_message(self) -> dict[str, Any]:
        item: dict[str, Any] = {"key": self.slot}
        if self.media:
            item["media"] = self.media
        else:
            if self.mods:
                item["mods"] = list(self.mods)
            if self.code:
                item["code"] = self.code
        return item


def msg_set_fallback(bindings: list[FallbackBinding], replace: bool = True) -> dict[str, Any]:
    return {
        "type": "set_fallback",
        "replace": replace,
        "bindings": [b.to_message() for b in bindings[:12]],
    }


def msg_reboot(bootloader: bool = False) -> dict[str, Any]:
    return {"type": "reboot", "bootloader": bootloader}


def msg_test_mode(enable: bool) -> dict[str, Any]:
    return {"type": "test_mode", "enable": enable}


# --------------------------------------------------------------------------- urządzenie → PC


@dataclass(frozen=True)
class DeviceInfo:
    device: str
    fw: str
    board: str
    keys: int = KEY_COUNT
    encoder: bool = True
    hid: bool = True

    @property
    def board_name(self) -> str:
        return BOARD_NAMES.get(self.board, self.board)


@dataclass(frozen=True)
class KeyEvent:
    key: int
    down: bool
    t: int


@dataclass(frozen=True)
class EncoderEvent:
    steps: int
    t: int


@dataclass(frozen=True)
class AckEvent:
    id: int


@dataclass(frozen=True)
class ErrorEvent:
    id: int | None
    msg: str


@dataclass(frozen=True)
class LogEvent:
    level: str
    msg: str


@dataclass(frozen=True)
class TestModeEvent:
    active: bool


DeviceMessage = (
    DeviceInfo | KeyEvent | EncoderEvent | AckEvent | ErrorEvent | LogEvent | TestModeEvent
)


def _int(data: dict[str, Any], key: str, default: int | None = None) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{key}: int expected")
    return value


def parse_device_message(data: dict[str, Any]) -> DeviceMessage | None:
    """Zamienia słownik od urządzenia na obiekt. Nieznany typ → None (ignorujemy)."""
    kind = data.get("type")
    if kind == "hello":
        device = data.get("device")
        if device != "tap32":
            raise ProtocolError("not a tap32 device")
        return DeviceInfo(
            device=device,
            fw=str(data.get("fw", "?")),
            board=str(data.get("board", "?")),
            keys=_int(data, "keys", KEY_COUNT),
            encoder=bool(data.get("encoder", True)),
            hid=bool(data.get("hid", True)),
        )
    if kind == "key":
        key = _int(data, "key")
        if not 1 <= key <= KEY_COUNT:
            raise ProtocolError("key out of range")
        action = data.get("action")
        if action not in ("down", "up"):
            raise ProtocolError("bad key action")
        return KeyEvent(key=key, down=action == "down", t=_int(data, "t", 0))
    if kind == "enc":
        return EncoderEvent(steps=_int(data, "steps"), t=_int(data, "t", 0))
    if kind == "ack":
        return AckEvent(id=_int(data, "id"))
    if kind == "error":
        raw_id = data.get("id")
        return ErrorEvent(
            id=raw_id if isinstance(raw_id, int) else None, msg=str(data.get("msg", ""))
        )
    if kind == "log":
        return LogEvent(level=str(data.get("level", "info")), msg=str(data.get("msg", "")))
    if kind == "test":
        return TestModeEvent(active=bool(data.get("active", False)))
    return None
