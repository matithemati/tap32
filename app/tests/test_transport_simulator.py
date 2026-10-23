"""Transport szeregowy (atrapa portu), wykrywanie portów i symulator urządzenia."""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from typing import Any

from tap32.core import protocol
from tap32.core.simulator import SimulatedDevice, SimulatorTransport
from tap32.core.transport import ConnectionState, SerialTransport, candidate_ports
from tests.conftest import ManualClock


@dataclass
class PortInfo:
    device: str
    vid: int | None = None
    product: str | None = None
    manufacturer: str | None = None
    description: str | None = None


def test_candidate_ports_prefers_product_name() -> None:
    ports = [
        PortInfo("COM1", vid=0x1234, description="Bluetooth"),
        PortInfo("COM5", vid=0x239A, description="USB Serial Device"),
        PortInfo("COM9", vid=0x2E8A, product="Tap32"),
        PortInfo("COM7", vid=0x303A),
    ]
    assert candidate_ports(ports) == ["COM9", "COM5", "COM7"]


class FakeSerial:
    """Port szeregowy połączony z SimulatedDevice."""

    def __init__(self, device: SimulatedDevice) -> None:
        self.device = device
        self.rx: queue.Queue[bytes] = queue.Queue()
        device.emit = lambda msg: self.rx.put(protocol.encode(msg))
        self.port = ""
        self.is_open = False
        self.broken = False

    def open(self) -> None:
        if self.port != "COM9":
            raise OSError("no such port")
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def reset_input_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        if self.broken:
            raise OSError("unplugged")
        for line in data.splitlines():
            self.device.handle_line(line)
        return len(data)

    def readline(self) -> bytes:
        if self.broken:
            raise OSError("unplugged")
        try:
            return self.rx.get(timeout=0.02)
        except queue.Empty:
            return b""


def wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_serial_transport_detects_and_reconnects() -> None:
    device = SimulatedDevice(board="xiao_esp32s3")
    serials: list[FakeSerial] = []

    def factory() -> FakeSerial:
        s = FakeSerial(device)
        serials.append(s)
        return s

    transport = SerialTransport(
        serial_factory=factory,
        port_lister=lambda: ["COM3", "COM9"],
        hello_timeout=0.5,
        retry_interval=0.05,
    )
    states: list[ConnectionState] = []
    messages: list[dict[str, Any]] = []
    transport.on_state = lambda state, info, port: states.append(state)
    transport.on_message = messages.append
    transport.start()
    try:
        assert wait_for(lambda: transport.connected)
        assert transport.port_name == "COM9"
        assert transport.device_info is not None
        assert transport.device_info.board_name == "XIAO ESP32-S3"
        assert device.online

        device.press(3)
        assert wait_for(lambda: any(m.get("type") == "key" for m in messages))

        # Odłączenie kabla → rozłączenie → ponowne połączenie
        serials[-1].broken = True
        assert wait_for(lambda: ConnectionState.DISCONNECTED in states)
        assert wait_for(lambda: transport.connected and len(serials) >= 3)
    finally:
        transport.stop()


def test_simulated_device_protocol() -> None:
    clock = ManualClock()
    out: list[dict[str, Any]] = []
    device = SimulatedDevice(clock=clock, emit=out.append)
    clock.advance(2)
    assert device.screen().kind == "offline"

    device.handle({"type": "hello", "app": "x"})
    assert out[-1]["type"] == "hello" and out[-1]["device"] == "tap32"
    assert device.online

    device.handle({"type": "display", "mode": "grid", "title": "T", "labels": ["a", "b"], "id": 4})
    assert out[-1] == {"type": "ack", "id": 4}
    screen = device.screen()
    assert screen.kind == "grid" and screen.labels[:2] == ("a", "b") and screen.online

    device.handle({"type": "display", "mode": "bar", "title": "Vol", "value": 30, "ms": 500})
    assert device.screen().kind == "bar"
    clock.advance(0.6)
    device.handle({"type": "ping"})
    assert device.screen().kind == "grid"

    device.handle({"type": "settings", "brightness": 999, "id": 5})
    assert out[-1]["type"] == "error" and out[-1]["id"] == 5
    device.handle({"type": "unknown_future", "id": 6})
    assert out[-1]["type"] == "error"  # poprzednia wiadomość – nieznane typy bez odpowiedzi

    device.handle_line(b"{broken")
    assert out[-1] == {
        "type": "error",
        "msg": "invalid json: Expecting property name enclosed in double quotes",
    }

    clock.advance(3.5)  # brak ping → offline
    assert not device.online
    assert device.screen().kind == "offline"


def test_simulated_device_fallback_hid_when_offline() -> None:
    clock = ManualClock()
    device = SimulatedDevice(clock=clock)
    device.handle(
        protocol.msg_set_fallback(
            [protocol.FallbackBinding(1, mods=("ctrl",), code="c")], replace=False
        )
    )
    clock.advance(5)
    device.press(1)
    device.rotate(2)
    assert device.hid_log == [
        "1: {'mods': ['ctrl'], 'code': 'c'}",
        "enc_cw: {'media': 'vol_up'}",
        "enc_cw: {'media': 'vol_up'}",
    ]


def test_simulator_transport_end_to_end() -> None:
    device = SimulatedDevice()
    transport = SimulatorTransport(device)
    received: list[dict[str, Any]] = []
    transport.on_message = received.append
    transport.start()
    assert transport.connected
    assert transport.port_name == "symulator"
    device.rotate(-1)
    assert received[-1]["type"] == "enc" and received[-1]["steps"] == -1
    assert transport.send(protocol.msg_flash("Hej", 1))
    assert device.screen().kind in ("flash", "splash")
