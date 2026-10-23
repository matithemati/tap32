"""Interfejs funkcji zależnych od systemu operacyjnego.

Implementacja dla Windows: windows.py. Inne systemy mogą dostarczyć własną klasę
(np. linux.py) – reszta aplikacji używa wyłącznie tego interfejsu.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger("tap32.platform")


class PlatformError(RuntimeError):
    pass


def pick_window(windows_z_order: list[int], foreground: int | None, cycle: bool) -> int | None:
    """Wybiera okno do aktywacji.

    windows_z_order – okna programu od najwyżej położonego (ostatnio używanego).
    Gdy aktywne jest już okno tego programu i cycle=True, wybierane jest okno najdawniej
    używane – kolejne wywołania obchodzą wszystkie okna po kolei.
    """
    if not windows_z_order:
        return None
    if cycle and foreground in windows_z_order and len(windows_z_order) > 1:
        return windows_z_order[-1]
    return windows_z_order[0]


class PlatformBackend(ABC):
    name = "abstract"

    # --- programy, pliki, adresy
    @abstractmethod
    def launch(self, path: str, args: str = "", cwd: str = "") -> None: ...

    @abstractmethod
    def focus_process(self, exe_name: str, cycle: bool = False) -> bool:
        """Przełącza na okno działającego procesu. Zwraca False, jeśli proces nie ma okna.

        cycle=True: gdy okno programu jest już aktywne, przechodzi do kolejnego okna programu.
        """

    @abstractmethod
    def open_path(self, path: str) -> None: ...

    @abstractmethod
    def open_url(self, url: str, browser: str = "") -> None: ...

    # --- klawiatura i mysz
    @abstractmethod
    def send_hotkey(self, keys: list[str]) -> None:
        """keys: nazwy klawiszy, np. ["ctrl", "shift", "c"] – wciśnięte razem."""

    @abstractmethod
    def type_text(self, text: str) -> None: ...

    @abstractmethod
    def media_key(self, name: str) -> None:
        """name: play_pause, next, prev, stop, vol_up, vol_down, mute."""

    @abstractmethod
    def scroll(self, dx: int, dy: int) -> None: ...

    # --- dźwięk
    @abstractmethod
    def get_system_volume(self) -> float | None:
        """0–100 albo None, gdy niedostępne."""

    @abstractmethod
    def change_system_volume(self, delta: float) -> float | None:
        """Zmienia głośność o delta punktów procentowych; zwraca nową wartość."""

    @abstractmethod
    def toggle_system_mute(self) -> bool | None:
        """Zwraca nowy stan wyciszenia."""

    @abstractmethod
    def change_app_volume(self, exe_name: str, delta: float) -> float | None:
        """Zmienia głośność procesu; zwraca nową wartość lub None, gdy proces nie gra."""

    @abstractmethod
    def toggle_app_mute(self, exe_name: str) -> bool | None: ...

    @abstractmethod
    def list_audio_processes(self) -> list[str]: ...

    # --- polecenia i system
    @abstractmethod
    def run_shell(self, command: str, shell: str, timeout_s: float, hidden: bool) -> int:
        """Zwraca kod wyjścia. Rzuca PlatformError przy przekroczeniu czasu."""

    @abstractmethod
    def lock_screen(self) -> None: ...

    @abstractmethod
    def screen_off(self) -> None: ...

    @abstractmethod
    def foreground_process(self) -> str | None:
        """Nazwa pliku wykonywalnego aktywnego okna (np. 'obs64.exe')."""

    # --- integracja z systemem
    @abstractmethod
    def get_autostart(self) -> bool: ...

    @abstractmethod
    def set_autostart(self, enabled: bool, command: str) -> None: ...

    def thread_init(self) -> None:  # noqa: B027 - opcjonalny hak
        """Inicjalizacja wątku roboczego (np. COM na Windows)."""


class NullPlatform(PlatformBackend):
    """Implementacja „nic nie rób” – dla nieobsługiwanych systemów i testów."""

    name = "null"

    def _skip(self, what: str) -> None:
        log.info("[%s] %s – nieobsługiwane na tej platformie", self.name, what)

    def launch(self, path: str, args: str = "", cwd: str = "") -> None:
        self._skip(f"launch {path}")

    def focus_process(self, exe_name: str, cycle: bool = False) -> bool:
        return False

    def open_path(self, path: str) -> None:
        self._skip(f"open {path}")

    def open_url(self, url: str, browser: str = "") -> None:
        import webbrowser

        webbrowser.open(url)

    def send_hotkey(self, keys: list[str]) -> None:
        self._skip(f"hotkey {'+'.join(keys)}")

    def type_text(self, text: str) -> None:
        self._skip("type_text")

    def media_key(self, name: str) -> None:
        self._skip(f"media {name}")

    def scroll(self, dx: int, dy: int) -> None:
        self._skip("scroll")

    def get_system_volume(self) -> float | None:
        return None

    def change_system_volume(self, delta: float) -> float | None:
        return None

    def toggle_system_mute(self) -> bool | None:
        return None

    def change_app_volume(self, exe_name: str, delta: float) -> float | None:
        return None

    def toggle_app_mute(self, exe_name: str) -> bool | None:
        return None

    def list_audio_processes(self) -> list[str]:
        return []

    def run_shell(self, command: str, shell: str, timeout_s: float, hidden: bool) -> int:
        import subprocess

        try:
            return subprocess.run(command, shell=True, timeout=timeout_s, check=False).returncode
        except subprocess.TimeoutExpired as exc:
            raise PlatformError(f"przekroczono limit czasu {timeout_s} s") from exc

    def lock_screen(self) -> None:
        self._skip("lock")

    def screen_off(self) -> None:
        self._skip("screen_off")

    def foreground_process(self) -> str | None:
        return None

    def get_autostart(self) -> bool:
        return False

    def set_autostart(self, enabled: bool, command: str) -> None:
        self._skip("autostart")
