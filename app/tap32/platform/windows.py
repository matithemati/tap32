"""Implementacja funkcji systemowych dla Windows 10/11."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import shlex
import subprocess
import threading
import time
import winreg
from typing import Any

import psutil

from .base import PlatformBackend, PlatformError

log = logging.getLogger("tap32.platform")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Tap32"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010


def _pynput_key(name: str) -> Any:
    from pynput.keyboard import Key, KeyCode

    special = {
        "ctrl": Key.ctrl, "shift": Key.shift, "alt": Key.alt, "win": Key.cmd,
        "enter": Key.enter, "esc": Key.esc, "tab": Key.tab, "space": Key.space,
        "backspace": Key.backspace, "delete": Key.delete, "insert": Key.insert,
        "home": Key.home, "end": Key.end, "pageup": Key.page_up, "pagedown": Key.page_down,
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "capslock": Key.caps_lock, "printscreen": Key.print_screen,
        "scrolllock": Key.scroll_lock, "pause": Key.pause, "menu": Key.menu,
        "numlock": Key.num_lock,
        "media_play_pause": Key.media_play_pause, "media_next": Key.media_next,
        "media_prev": Key.media_previous, "media_stop": Key.media_stop,
        "media_vol_up": Key.media_volume_up, "media_vol_down": Key.media_volume_down,
        "media_mute": Key.media_volume_mute,
    }  # fmt: skip
    if name in special:
        return special[name]
    if name.startswith("f") and name[1:].isdigit():
        return getattr(Key, name)
    if name == "plus":
        return KeyCode.from_char("+")
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise PlatformError(f"nieznany klawisz {name}")


MEDIA_TO_PYNPUT = {
    "play_pause": "media_play_pause",
    "next": "media_next",
    "prev": "media_prev",
    "stop": "media_stop",
    "vol_up": "media_vol_up",
    "vol_down": "media_vol_down",
    "mute": "media_mute",
}


class WindowsPlatform(PlatformBackend):
    name = "windows"

    def __init__(self) -> None:
        self._kb_lock = threading.Lock()
        self._keyboard: Any = None
        self._mouse: Any = None

    def thread_init(self) -> None:
        try:
            import comtypes

            comtypes.CoInitialize()
        except Exception as exc:
            log.debug("CoInitialize: %s", exc)

    # ------------------------------------------------------------------ programy

    def launch(self, path: str, args: str = "", cwd: str = "") -> None:
        try:
            os.startfile(path, "open", args, cwd or None)  # type: ignore[attr-defined,call-arg]
        except OSError:
            # Awaryjnie: bezpośrednie uruchomienie (np. ścieżki z argumentami)
            argv = [path, *shlex.split(args, posix=False)] if args else [path]
            subprocess.Popen(argv, cwd=cwd or None, close_fds=True)

    def focus_process(self, exe_name: str) -> bool:
        import win32con
        import win32gui
        import win32process

        target = exe_name.lower()
        pids = {
            p.info["pid"]
            for p in psutil.process_iter(["pid", "name"])
            if (p.info.get("name") or "").lower() == target
        }
        if not pids:
            return False
        windows: list[int] = []

        def collect(hwnd: int, _: Any) -> bool:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in pids and not win32gui.GetWindow(hwnd, win32con.GW_OWNER):
                    windows.append(hwnd)
            return True

        win32gui.EnumWindows(collect, None)
        if not windows:
            return False  # proces działa w tle bez okna – uruchomimy nową instancję
        hwnd = windows[0]
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # Windows blokuje SetForegroundWindow z tła; naciśnięcie Alt to obchodzi.
            import win32api

            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as exc:
            log.debug("Nie udało się przełączyć okna: %s", exc)
        return True

    def open_path(self, path: str) -> None:
        if not os.path.exists(path):
            raise PlatformError(f"nie istnieje: {path}")
        os.startfile(path)  # type: ignore[attr-defined]

    def open_url(self, url: str, browser: str = "") -> None:
        if browser:
            os.startfile(browser, "open", url)  # type: ignore[attr-defined,call-arg]
        else:
            os.startfile(url)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ klawiatura i mysz

    def _kb(self) -> Any:
        if self._keyboard is None:
            from pynput.keyboard import Controller

            self._keyboard = Controller()
        return self._keyboard

    def send_hotkey(self, keys: list[str]) -> None:
        resolved = [_pynput_key(k) for k in keys]
        kb = self._kb()
        with self._kb_lock:
            pressed = []
            try:
                for key in resolved:
                    kb.press(key)
                    pressed.append(key)
                time.sleep(0.01)
            finally:
                for key in reversed(pressed):
                    kb.release(key)

    def type_text(self, text: str) -> None:
        with self._kb_lock:
            self._kb().type(text)

    def media_key(self, name: str) -> None:
        key = _pynput_key(MEDIA_TO_PYNPUT[name])
        with self._kb_lock:
            self._kb().press(key)
            self._kb().release(key)

    def scroll(self, dx: int, dy: int) -> None:
        if self._mouse is None:
            from pynput.mouse import Controller

            self._mouse = Controller()
        self._mouse.scroll(dx, dy)

    # ------------------------------------------------------------------ dźwięk

    @staticmethod
    def _endpoint() -> Any:
        from pycaw.pycaw import AudioUtilities

        speakers = AudioUtilities.GetSpeakers()
        endpoint = getattr(speakers, "EndpointVolume", None)
        if endpoint is not None:
            return endpoint
        # Starsze pycaw
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume

        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)

    def get_system_volume(self) -> float | None:
        try:
            return float(self._endpoint().GetMasterVolumeLevelScalar()) * 100
        except Exception as exc:
            log.debug("Głośność niedostępna: %s", exc)
            return None

    def change_system_volume(self, delta: float) -> float | None:
        try:
            endpoint = self._endpoint()
            value = float(endpoint.GetMasterVolumeLevelScalar()) * 100
            value = max(0.0, min(100.0, value + delta))
            endpoint.SetMasterVolumeLevelScalar(value / 100, None)
            if delta > 0 and endpoint.GetMute():
                endpoint.SetMute(0, None)
            return value
        except Exception as exc:
            log.debug("Zmiana głośności nieudana: %s", exc)
            return None

    def toggle_system_mute(self) -> bool | None:
        try:
            endpoint = self._endpoint()
            muted = not bool(endpoint.GetMute())
            endpoint.SetMute(int(muted), None)
            return muted
        except Exception as exc:
            log.debug("Wyciszenie nieudane: %s", exc)
            return None

    @staticmethod
    def _sessions(exe_name: str) -> list[Any]:
        from pycaw.pycaw import AudioUtilities

        target = exe_name.lower()
        return [
            s
            for s in AudioUtilities.GetAllSessions()
            if s.Process is not None and s.Process.name().lower() == target
        ]

    def change_app_volume(self, exe_name: str, delta: float) -> float | None:
        sessions = self._sessions(exe_name)
        if not sessions:
            return None
        current = float(sessions[0].SimpleAudioVolume.GetMasterVolume()) * 100
        value = max(0.0, min(100.0, current + delta))
        for session in sessions:
            session.SimpleAudioVolume.SetMasterVolume(value / 100, None)
            if delta > 0 and session.SimpleAudioVolume.GetMute():
                session.SimpleAudioVolume.SetMute(0, None)
        return value

    def toggle_app_mute(self, exe_name: str) -> bool | None:
        sessions = self._sessions(exe_name)
        if not sessions:
            return None
        muted = not bool(sessions[0].SimpleAudioVolume.GetMute())
        for session in sessions:
            session.SimpleAudioVolume.SetMute(int(muted), None)
        return muted

    def list_audio_processes(self) -> list[str]:
        from pycaw.pycaw import AudioUtilities

        names = {s.Process.name() for s in AudioUtilities.GetAllSessions() if s.Process is not None}
        return sorted(names, key=str.lower)

    # ------------------------------------------------------------------ polecenia i system

    def run_shell(self, command: str, shell: str, timeout_s: float, hidden: bool) -> int:
        if shell == "powershell":
            argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
        else:
            argv = ["cmd", "/c", command]
        flags = CREATE_NO_WINDOW if hidden else CREATE_NEW_CONSOLE
        try:
            result = subprocess.run(argv, timeout=timeout_s, creationflags=flags, check=False)
        except subprocess.TimeoutExpired as exc:
            raise PlatformError(f"przekroczono limit czasu {timeout_s} s") from exc
        return result.returncode

    def lock_screen(self) -> None:
        ctypes.windll.user32.LockWorkStation()

    def screen_off(self) -> None:
        hwnd_broadcast, wm_syscommand, sc_monitorpower = 0xFFFF, 0x0112, 0xF170
        ctypes.windll.user32.PostMessageW(hwnd_broadcast, wm_syscommand, sc_monitorpower, 2)

    def foreground_process(self) -> str | None:
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            return str(psutil.Process(pid).name())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    # ------------------------------------------------------------------ autostart

    def get_autostart(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_VALUE)
                return True
        except OSError:
            return False

    def set_autostart(self, enabled: bool, command: str) -> None:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
            else:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, RUN_VALUE)
