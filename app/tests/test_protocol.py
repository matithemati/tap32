from __future__ import annotations

import pytest

from tap32.core import protocol
from tap32.core.protocol import (
    DeviceInfo,
    EncoderEvent,
    ErrorEvent,
    FallbackBinding,
    KeyEvent,
    ProtocolError,
)


def test_encode_decode_roundtrip() -> None:
    msg = protocol.msg_flash("Spotify", key=3, ms=1200)
    data = protocol.encode(msg)
    assert data.endswith(b"\n")
    assert protocol.decode(data) == {"type": "flash", "text": "Spotify", "ms": 1200, "key": 3}


@pytest.mark.parametrize("line", [b"", b"{oops", b"[1,2]", b'{"x":1}', b"\xff\xfe"])
def test_decode_rejects_invalid(line: bytes) -> None:
    with pytest.raises(ProtocolError):
        protocol.decode(line)


def test_encode_too_long() -> None:
    with pytest.raises(ProtocolError):
        protocol.encode({"type": "x", "data": "a" * 2000})


def test_transliteration() -> None:
    assert protocol.transliterate("Zażółć gęślą jaźń") == "Zazolc gesla jazn"
    assert protocol.transliterate("Głośność…") == "Glosnosc..."
    assert protocol.fit("Przeglądarka", 7) == "Przegla"


def test_display_grid_pads_and_truncates() -> None:
    msg = protocol.msg_display_grid("Domyślny", ["Kalkulator", "Łódź"])
    assert msg["title"] == "Domyslny"
    assert msg["labels"][:2] == ["Kalkula", "Lodz"]
    assert len(msg["labels"]) == 9
    assert msg["labels"][8] == ""


def test_display_bar_clamps() -> None:
    assert protocol.msg_display_bar("Vol", 150)["value"] == 100
    assert protocol.msg_display_bar("Vol", -3)["value"] == 0
    assert protocol.msg_display_bar("Vol", 42.6, ms=0) == {
        "type": "display",
        "mode": "bar",
        "title": "Vol",
        "value": 43,
    }


def test_settings_validation() -> None:
    assert protocol.msg_settings(brightness=10, flip=True) == {
        "type": "settings",
        "brightness": 10,
        "flip": True,
    }
    with pytest.raises(ProtocolError):
        protocol.msg_settings(brightness=300)
    with pytest.raises(ProtocolError):
        protocol.msg_settings(flip=1)
    with pytest.raises(ProtocolError):
        protocol.msg_settings(enc_pulses=True)
    with pytest.raises(ProtocolError):
        protocol.msg_settings(color="red")


def test_set_fallback_message() -> None:
    msg = protocol.msg_set_fallback(
        [
            FallbackBinding(1, mods=("ctrl", "shift"), code="c"),
            FallbackBinding("enc_cw", media="vol_up"),
            FallbackBinding(5),
        ]
    )
    assert msg == {
        "type": "set_fallback",
        "replace": True,
        "bindings": [
            {"key": 1, "mods": ["ctrl", "shift"], "code": "c"},
            {"key": "enc_cw", "media": "vol_up"},
            {"key": 5},
        ],
    }


def test_parse_device_messages() -> None:
    info = protocol.parse_device_message(
        {"type": "hello", "device": "tap32", "fw": "1.0.0", "board": "xiao_esp32s3", "keys": 10}
    )
    assert isinstance(info, DeviceInfo)
    assert info.board_name == "XIAO ESP32-S3"
    assert protocol.parse_device_message(
        {"type": "key", "key": 10, "action": "up", "t": 5}
    ) == KeyEvent(10, False, 5)
    assert protocol.parse_device_message({"type": "enc", "steps": -3, "t": 9}) == EncoderEvent(
        -3, 9
    )
    assert protocol.parse_device_message({"type": "error", "msg": "invalid json"}) == ErrorEvent(
        None, "invalid json"
    )
    assert protocol.parse_device_message({"type": "brand_new", "x": 1}) is None


@pytest.mark.parametrize(
    "msg",
    [
        {"type": "hello", "device": "other"},
        {"type": "key", "key": 11, "action": "down"},
        {"type": "key", "key": 1, "action": "pressed"},
        {"type": "enc", "steps": "2"},
        {"type": "key", "key": True, "action": "down"},
    ],
)
def test_parse_device_message_invalid(msg: dict) -> None:
    with pytest.raises(ProtocolError):
        protocol.parse_device_message(msg)
