"""Wspólne atrapy: platforma, zegar, transport."""

from __future__ import annotations

from typing import Any

import pytest

from tap32.core.actions import ActionExecutor
from tap32.core.transport import ConnectionState, Transport
from tap32.platform.base import PlatformBackend


class FakePlatform(PlatformBackend):
    """Zapisuje wywołania zamiast działać na systemie."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.volume = 50.0
        self.muted = False
        self.app_volumes: dict[str, float] = {"spotify.exe": 40.0}
        self.running: set[str] = set()
        self.foreground: str | None = None

    def launch(self, path: str, args: str = "", cwd: str = "") -> None:
        self.calls.append(("launch", path, args, cwd))

    def focus_process(self, exe_name: str, cycle: bool = False) -> bool:
        if exe_name.lower() in self.running:
            self.calls.append(("focus", exe_name, cycle))
            return True
        return False

    def open_path(self, path: str) -> None:
        self.calls.append(("open", path))

    def open_url(self, url: str, browser: str = "") -> None:
        self.calls.append(("url", url, browser))

    def send_hotkey(self, keys: list[str]) -> None:
        self.calls.append(("hotkey", tuple(keys)))

    def type_text(self, text: str) -> None:
        self.calls.append(("type", text))

    def media_key(self, name: str) -> None:
        self.calls.append(("media", name))

    def scroll(self, dx: int, dy: int) -> None:
        self.calls.append(("scroll", dx, dy))

    def get_system_volume(self) -> float | None:
        return self.volume

    def change_system_volume(self, delta: float) -> float | None:
        self.volume = max(0.0, min(100.0, self.volume + delta))
        self.calls.append(("volume", delta))
        return self.volume

    def toggle_system_mute(self) -> bool | None:
        self.muted = not self.muted
        self.calls.append(("mute", self.muted))
        return self.muted

    def change_app_volume(self, exe_name: str, delta: float) -> float | None:
        if exe_name not in self.app_volumes:
            return None
        value = max(0.0, min(100.0, self.app_volumes[exe_name] + delta))
        self.app_volumes[exe_name] = value
        self.calls.append(("app_volume", exe_name, delta))
        return value

    def toggle_app_mute(self, exe_name: str) -> bool | None:
        self.calls.append(("app_mute", exe_name))
        return True if exe_name in self.app_volumes else None

    def list_audio_processes(self) -> list[str]:
        return list(self.app_volumes)

    def run_shell(self, command: str, shell: str, timeout_s: float, hidden: bool) -> int:
        self.calls.append(("shell", command, shell))
        return 0

    def lock_screen(self) -> None:
        self.calls.append(("lock",))

    def screen_off(self) -> None:
        self.calls.append(("screen_off",))

    def foreground_process(self) -> str | None:
        return self.foreground

    def get_autostart(self) -> bool:
        return False

    def set_autostart(self, enabled: bool, command: str) -> None:
        self.calls.append(("autostart", enabled))


class FakeHost:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def switch_profile(self, name: str) -> None:
        self.calls.append(("switch", name))

    def next_profile(self) -> None:
        self.calls.append(("next",))

    def prev_profile(self) -> None:
        self.calls.append(("prev",))

    def show_bar(self, title: str, value: float) -> None:
        self.calls.append(("bar", title, round(value)))

    def show_text(self, line1: str, line2: str = "", ms: int = 1500) -> None:
        self.calls.append(("text", line1, line2))


class ManualClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[dict[str, Any]] = []

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def send(self, message: dict[str, Any]) -> bool:
        self.sent.append(message)
        return self.connected

    def connect(self) -> None:
        self.state = ConnectionState.CONNECTED

    def of_type(self, kind: str) -> list[dict[str, Any]]:
        return [m for m in self.sent if m["type"] == kind]


@pytest.fixture
def platform() -> FakePlatform:
    return FakePlatform()


@pytest.fixture
def host() -> FakeHost:
    return FakeHost()


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def sync_executor() -> ActionExecutor:
    return ActionExecutor(synchronous=True)
