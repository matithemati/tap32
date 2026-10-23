"""Aktywny profil, warstwy i automatyczne przełączanie według aktywnego procesu."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from .actions import ActionBase, MacroStep
from .actions.builtin import LayerAction, MacroAction, ProfileAction
from .config import Config, Profile

log = logging.getLogger("tap32.profiles")

ProfileListener = Callable[[Profile, str], None]  # (efektywny profil, powód)


class ProfileManager:
    def __init__(self, config: Config) -> None:
        self._lock = threading.RLock()
        self._listeners: list[ProfileListener] = []
        self.config = config
        config.ensure_valid()
        self._active = config.default_profile
        self._manual = config.default_profile  # profil wybrany ręcznie (powrót po auto)
        self._auto = False
        self._layers: list[tuple[int, str]] = []  # (klawisz, profil)
        self._last_process: str | None = None

    # ------------------------------------------------------------------ odczyt

    def add_listener(self, listener: ProfileListener) -> None:
        self._listeners.append(listener)

    @property
    def active(self) -> Profile:
        with self._lock:
            profile = self.config.profile(self._active)
            if profile is None:
                self.config.ensure_valid()
                self._active = self.config.default_profile
                profile = self.config.profile(self._active)
            assert profile is not None
            return profile

    @property
    def effective(self) -> Profile:
        """Profil używany do akcji: najwyższa warstwa albo aktywny profil."""
        with self._lock:
            for _, name in reversed(self._layers):
                layer = self.config.profile(name)
                if layer is not None:
                    return layer
            return self.active

    @property
    def is_auto(self) -> bool:
        return self._auto

    # ------------------------------------------------------------------ zmiany

    def set_active(self, name: str, reason: str = "manual") -> bool:
        with self._lock:
            if self.config.profile(name) is None:
                log.warning("Nie ma profilu „%s”", name)
                return False
            if reason == "manual":
                self._manual = name
                self._auto = False
            elif reason == "auto":
                self._auto = True
            changed = name != self._active
            self._active = name
        if changed or reason == "manual":
            log.info("Profil: %s (%s)", name, reason)
            self._notify(reason)
        return True

    def _step(self, delta: int) -> None:
        with self._lock:
            names = self.config.profile_names()
            if not names:
                return
            index = names.index(self._active) if self._active in names else 0
            target = names[(index + delta) % len(names)]
        self.set_active(target, "manual")

    def next(self) -> None:
        self._step(1)

    def prev(self) -> None:
        self._step(-1)

    def push_layer(self, key: int, name: str) -> None:
        with self._lock:
            if self.config.profile(name) is None:
                log.warning("Warstwa: nie ma profilu „%s”", name)
                return
            self._layers.append((key, name))
        self._notify("layer")

    def pop_layer(self, key: int) -> None:
        with self._lock:
            before = len(self._layers)
            self._layers = [(k, n) for k, n in self._layers if k != key]
            changed = len(self._layers) != before
        if changed:
            self._notify("layer")

    def clear_layers(self) -> None:
        with self._lock:
            had = bool(self._layers)
            self._layers.clear()
        if had:
            self._notify("layer")

    def on_foreground(self, exe: str | None) -> None:
        """Wywoływane przy zmianie aktywnego okna."""
        if exe == self._last_process:
            return
        self._last_process = exe
        if not self.config.settings.app.auto_switch or not exe:
            return
        match = next((p for p in self.config.profiles if p.matches_process(exe)), None)
        if match is not None:
            if match.name != self._active:
                self.set_active(match.name, "auto")
        elif self._auto:
            with self._lock:
                self._auto = False
                target = self._manual
            self.set_active(target, "auto-return")

    def refresh(self) -> None:
        """Po edycji konfiguracji: poprawia nieistniejące nazwy i powiadamia słuchaczy."""
        with self._lock:
            self.config.ensure_valid()
            if self.config.profile(self._active) is None:
                self._active = self.config.default_profile
            if self.config.profile(self._manual) is None:
                self._manual = self.config.default_profile
            self._layers = [(k, n) for k, n in self._layers if self.config.profile(n)]
        self._notify("config")

    def rename(self, old: str, new: str) -> None:
        """Zmienia nazwę profilu wraz z odwołaniami w akcjach profile/layer."""
        with self._lock:
            profile = self.config.profile(old)
            if profile is None or old == new:
                return
            profile.name = new
            for p in self.config.profiles:
                for binding in p.keys.values():
                    for action in binding.actions():
                        _rename_refs(action, old, new)
                for gesture in ("rotate_cw", "rotate_ccw", "press_rotate_cw", "press_rotate_ccw"):
                    enc_action = p.encoder.action_for(gesture)
                    if enc_action is not None:
                        _rename_refs(enc_action, old, new)
            if self.config.default_profile == old:
                self.config.default_profile = new
            if self._active == old:
                self._active = new
            if self._manual == old:
                self._manual = new
            self._layers = [(k, new if n == old else n) for k, n in self._layers]
        self._notify("config")

    def _notify(self, reason: str) -> None:
        profile = self.effective
        for listener in list(self._listeners):
            try:
                listener(profile, reason)
            except Exception:
                log.exception("Błąd słuchacza zmiany profilu")


def _rename_refs(action: ActionBase, old: str, new: str) -> None:
    if isinstance(action, ProfileAction | LayerAction) and action.profile == old:
        action.profile = new
    elif isinstance(action, MacroAction):
        step: MacroStep
        for step in action.steps:
            _rename_refs(step.action, old, new)


class ForegroundWatcher:
    """Wątek sprawdzający aktywny proces co `interval` s."""

    def __init__(
        self,
        get_process: Callable[[], str | None],
        callback: Callable[[str | None], None],
        interval: float = 0.5,
    ) -> None:
        self._get_process = get_process
        self._callback = callback
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="tap32-foreground", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def poll_once(self) -> None:
        try:
            exe = self._get_process()
        except Exception as exc:
            log.debug("Nie udało się odczytać aktywnego procesu: %s", exc)
            return
        if exe != self._last:
            self._last = exe
            self._callback(exe)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self.poll_once()
