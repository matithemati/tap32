"""Kontroler Tap32: zdarzenia z urządzenia → gesty → akcje; profil → ekran i tryb awaryjny.

Wszystko, co zmienia stan, dzieje się w jednym wątku pętli kontrolera (kolejka zdarzeń).
Akcje wykonują się w puli wątków (ActionExecutor). Testy mogą wywoływać
`handle_message()` i `tick()` bezpośrednio, z własnym zegarem.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .. import __version__
from ..platform.base import PlatformBackend
from . import protocol
from .actions import ActionBase, ActionContext, ActionExecutor
from .actions.builtin import AppVolumeAction, LayerAction, MediaAction, ProfileAction
from .config import Config, ConfigStore, Profile
from .fallback import compute_fallback
from .gestures import KEY_GESTURES, Gesture, GestureConfig, GestureEngine, GestureEvent
from .profiles import ForegroundWatcher, ProfileManager
from .protocol import DeviceInfo, EncoderEvent, ErrorEvent, KeyEvent, LogEvent, TestModeEvent
from .transport import ConnectionState, Transport

log = logging.getLogger("tap32.engine")

SAVE_DELAY_S = 0.5


class ControllerListener:
    """Powiadomienia dla GUI (wołane z wątków roboczych – GUI musi przekazać do swojego)."""

    def connection_changed(
        self, connected: bool, info: DeviceInfo | None, port: str | None
    ) -> None:
        pass

    def raw_input(self, key: int | None, down: bool, steps: int) -> None:
        """key=None → obrót pokrętła o `steps`; inaczej klawisz 1–10 down/up."""

    def gesture(self, event: GestureEvent, action: ActionBase | None) -> None:
        pass

    def profile_changed(self, profile: Profile, reason: str) -> None:
        pass

    def action_finished(self, summary: str, error: BaseException | None) -> None:
        pass

    def test_mode_changed(self, active: bool) -> None:
        pass


@dataclass
class _Task:
    kind: str
    payload: Any = None


class Controller:
    def __init__(
        self,
        config: Config,
        transport: Transport,
        platform: PlatformBackend,
        store: ConfigStore | None = None,
        executor: ActionExecutor | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.transport = transport
        self.platform = platform
        self.store = store
        self.clock = clock
        self.executor = executor or ActionExecutor(thread_init=platform.thread_init)
        self.listeners: list[ControllerListener] = []
        self.paused = False
        self.device_info: DeviceInfo | None = None

        self.profiles = ProfileManager(config)
        self.profiles.add_listener(self._on_profile_changed)
        self.gestures = GestureEngine(
            self._gesture_config(), emit=self._on_gesture, has_gesture=self._has_gesture
        )
        self._layer_keys: set[int] = set()
        self._queue: queue.Queue[_Task] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_ping = 0.0
        self._save_due: float | None = None
        self._next_id = 1
        self._watcher = ForegroundWatcher(platform.foreground_process, self._on_foreground)

        transport.on_message = lambda message: self._queue.put(_Task("message", message))
        transport.on_state = lambda state, info, port: self._queue.put(
            _Task("state", (state, info, port))
        )

    # ------------------------------------------------------------------ cykl życia

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="tap32-engine", daemon=True)
        self._thread.start()
        self.transport.start()
        self._watcher.start()

    def stop(self) -> None:
        self._running = False
        self._watcher.stop()
        self._queue.put(_Task("stop"))
        self.transport.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.flush_save()
        self.executor.shutdown()

    def _loop(self) -> None:
        while self._running:
            timeout = self._next_timeout()
            try:
                task = self._queue.get(timeout=timeout)
            except queue.Empty:
                task = None
            try:
                if task is not None:
                    self._handle_task(task)
                self.tick()
            except Exception:
                log.exception("Błąd w pętli kontrolera")

    def _next_timeout(self) -> float:
        now = self._now_ms()
        candidates = [protocol.PING_INTERVAL_S]
        deadline = self.gestures.next_deadline()
        if deadline is not None:
            candidates.append(max(0.0, (deadline - now) / 1000))
        if self._save_due is not None:
            candidates.append(max(0.0, self._save_due - self.clock()))
        return max(0.005, min(candidates))

    def _handle_task(self, task: _Task) -> None:
        if task.kind == "message":
            self.handle_message(task.payload)
        elif task.kind == "state":
            self.handle_state(*task.payload)
        elif task.kind == "call":
            task.payload()

    def call_soon(self, fn: Callable[[], object]) -> None:
        """Wykonaj funkcję w wątku kontrolera (np. z GUI)."""
        if self._running:
            self._queue.put(_Task("call", fn))
        else:
            fn()

    def _now_ms(self) -> float:
        return self.clock() * 1000

    # ------------------------------------------------------------------ zdarzenia z urządzenia

    def handle_state(
        self, state: ConnectionState, info: DeviceInfo | None, port: str | None
    ) -> None:
        if state == ConnectionState.CONNECTED:
            self.device_info = info
            self.gestures.reset()
            self.push_device_state()
            self._notify(lambda li: li.connection_changed(True, info, port))
        elif state == ConnectionState.DISCONNECTED:
            self.device_info = None
            self.gestures.reset()
            self._release_layers()
            self._notify(lambda li: li.connection_changed(False, None, None))

    def handle_message(self, message: dict[str, Any]) -> None:
        try:
            event = protocol.parse_device_message(message)
        except protocol.ProtocolError as exc:
            log.debug("Niepoprawna wiadomość od urządzenia: %s", exc)
            return
        now = self._now_ms()
        if isinstance(event, KeyEvent):
            self._notify(lambda li: li.raw_input(event.key, event.down, 0))
            self._on_key(event.key, event.down, now)
        elif isinstance(event, EncoderEvent):
            self._notify(lambda li: li.raw_input(None, True, event.steps))
            self.gestures.rotate(event.steps, now)
        elif isinstance(event, DeviceInfo):
            # hello po restarcie urządzenia – wyślij stan ponownie
            if self.device_info is not None:
                self.device_info = event
                self.push_device_state()
        elif isinstance(event, ErrorEvent):
            log.warning("Urządzenie zgłosiło błąd (id=%s): %s", event.id, event.msg)
        elif isinstance(event, LogEvent):
            log.info("[urządzenie] %s", event.msg)
        elif isinstance(event, TestModeEvent):
            self._notify(lambda li: li.test_mode_changed(event.active))

    def _on_key(self, key: int, down: bool, now: float) -> None:
        if down:
            binding = self.profiles.effective.keys[key]
            layer = next((a for a in binding.actions() if isinstance(a, LayerAction)), None)
            if layer is not None:
                self._layer_keys.add(key)
                self.profiles.push_layer(key, layer.profile)
                return
            self.gestures.key_down(key, now)
        else:
            if key in self._layer_keys:
                self._layer_keys.discard(key)
                self.profiles.pop_layer(key)
                return
            self.gestures.key_up(key, now)

    def _release_layers(self) -> None:
        self._layer_keys.clear()
        self.profiles.clear_layers()

    def tick(self) -> None:
        now = self.clock()
        self.gestures.tick(now * 1000)
        if self.transport.connected and now - self._last_ping >= protocol.PING_INTERVAL_S:
            self._last_ping = now
            self.transport.send(protocol.msg_ping())
        if self._save_due is not None and now >= self._save_due:
            self.flush_save()

    # ------------------------------------------------------------------ gesty i akcje

    def _gesture_config(self) -> GestureConfig:
        g = self.config.settings.gestures
        e = self.config.settings.encoder
        return GestureConfig(
            hold_ms=g.hold_ms,
            double_tap_ms=g.double_tap_ms,
            hold_on_threshold=g.hold_on_threshold,
            accel_enabled=e.accel_enabled,
            accel_window_ms=e.accel_window_ms,
            accel_multiplier=e.accel_multiplier,
        )

    def _has_gesture(self, key: int, gesture: Gesture) -> bool:
        return self.profiles.effective.action_for(key, gesture) is not None

    def _on_gesture(self, event: GestureEvent) -> None:
        profile = self.profiles.effective
        action = profile.action_for(event.key, event.gesture)
        self._notify(lambda li: li.gesture(event, action))
        if action is None or isinstance(action, LayerAction):
            return
        if self.paused:
            log.info("Akcje wstrzymane – pominięto %s", action.summary())
            return
        label = profile.keys[event.key].label if event.key is not None else ""
        ctx = ActionContext(self.platform, self, steps=event.steps, key=event.key)
        ctx.extra["label"] = label
        ctx.extra["gesture"] = event.gesture
        log.info("%s %s → %s", _key_name(event.key), event.gesture, action.summary())
        self.executor.submit(action, ctx, self._after_action)

    def _after_action(
        self, action: ActionBase, ctx: ActionContext, error: BaseException | None
    ) -> None:
        self._notify(lambda li: li.action_finished(action.summary(), error))
        if error is not None:
            if ctx.key is not None:
                self.send(protocol.msg_flash("Blad!", ctx.key, 1000))
            return
        if (
            not self.config.settings.app.flash_on_action
            or ctx.key is None
            or ctx.extra.get("gesture") not in KEY_GESTURES
            or isinstance(action, ProfileAction | MediaAction | AppVolumeAction)
        ):
            return
        text = ctx.extra.get("label") or action.summary()
        self.send(protocol.msg_flash(text, ctx.key, 800))

    def test_action(self, action: ActionBase, key: int | None = None) -> None:
        """Wykonanie akcji z GUI (przycisk „Testuj”)."""
        ctx = ActionContext(self.platform, self, steps=1, key=key)
        ctx.extra["gesture"] = Gesture.TAP
        self.executor.submit(action, ctx, self._after_action)

    # ------------------------------------------------------------------ ActionHost

    def switch_profile(self, name: str) -> None:
        self.profiles.set_active(name, "manual")

    def next_profile(self) -> None:
        self.profiles.next()

    def prev_profile(self) -> None:
        self.profiles.prev()

    def show_bar(self, title: str, value: float) -> None:
        self.send(protocol.msg_display_bar(title, value, 1500))

    def show_text(self, line1: str, line2: str = "", ms: int = 1500) -> None:
        self.send(protocol.msg_display_text(line1, line2, ms))

    # ------------------------------------------------------------------ wysyłanie stanu

    def send(self, message: dict[str, Any], with_id: bool = False) -> bool:
        if with_id:
            message = {**message, "id": self._next_id}
            self._next_id += 1
        return self.transport.send(message)

    def push_device_state(self) -> None:
        """Ustawienia + ekran + skróty awaryjne (po połączeniu i po zmianach)."""
        self.send_settings()
        self.send_profile_state()

    def send_settings(self) -> None:
        d = self.config.settings.device
        self.send(
            protocol.msg_settings(
                brightness=d.brightness,
                screensaver_s=d.screensaver_s,
                flip=d.flip,
                enc_reverse=d.enc_reverse,
                enc_pulses=d.enc_pulses,
                debounce_ms=d.debounce_ms,
            ),
            with_id=True,
        )

    def send_profile_state(self, flash_name: bool = False) -> None:
        profile = self.profiles.effective
        if self.config.settings.device.display_mode == "profile":
            self.send(protocol.msg_display_profile(profile.name))
        else:
            self.send(protocol.msg_display_grid(profile.name, profile.labels()))
            if flash_name:
                self.send(protocol.msg_flash(profile.name, None, 700))
        bindings = compute_fallback(self.profiles.active, self.config.settings.fallback)
        self.send(protocol.msg_set_fallback(bindings, replace=True), with_id=True)

    def _on_profile_changed(self, profile: Profile, reason: str) -> None:
        self.send_profile_state(flash_name=reason in ("manual", "auto", "auto-return"))
        self._notify(lambda li: li.profile_changed(profile, reason))

    def _on_foreground(self, exe: str | None) -> None:
        self.call_soon(lambda: self.profiles.on_foreground(exe))

    # ------------------------------------------------------------------ zmiany konfiguracji

    def config_changed(self, device_settings: bool = False) -> None:
        """Wywoływane przez GUI po edycji konfiguracji."""

        def apply() -> None:
            self.gestures.config = self._gesture_config()
            self.profiles.refresh()  # wysyła display + set_fallback
            if device_settings:
                self.send_settings()
            self.schedule_save()

        self.call_soon(apply)

    def schedule_save(self) -> None:
        self._save_due = self.clock() + SAVE_DELAY_S
        if not self._running:
            self.flush_save()

    def flush_save(self) -> None:
        self._save_due = None
        if self.store is None:
            return
        try:
            self.store.save(self.config)
        except OSError as exc:
            log.error("Nie zapisano konfiguracji: %s", exc)

    def set_test_mode(self, enable: bool) -> None:
        self.send(protocol.msg_test_mode(enable))

    def reboot_device(self, bootloader: bool = False) -> None:
        self.send(protocol.msg_reboot(bootloader), with_id=True)

    # ------------------------------------------------------------------ pomocnicze

    def add_listener(self, listener: ControllerListener) -> None:
        self.listeners.append(listener)

    def _notify(self, fn: Callable[[ControllerListener], None]) -> None:
        for listener in list(self.listeners):
            try:
                fn(listener)
            except Exception:
                log.exception("Błąd słuchacza kontrolera")


def _key_name(key: int | None) -> str:
    if key is None:
        return "Pokrętło"
    if key == protocol.ENCODER_KEY:
        return "Przycisk pokrętła"
    return f"K{key}"


__all__ = ["Controller", "ControllerListener", "__version__"]
