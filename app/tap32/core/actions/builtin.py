"""Wbudowane typy akcji Tap32."""

from __future__ import annotations

import time
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator

from ...platform.base import PlatformError
from .base import Action, ActionBase, ActionContext, log, register_action

MAX_MACRO_DEPTH = 5

# Kanoniczne nazwy klawiszy dla akcji hotkey (i nagrywania skrótów w GUI).
MODIFIER_KEYS = ("ctrl", "shift", "alt", "win")
SPECIAL_KEYS = (
    "enter", "esc", "tab", "space", "backspace", "delete", "insert", "home", "end",
    "pageup", "pagedown", "up", "down", "left", "right", "capslock", "printscreen",
    "scrolllock", "pause", "menu", "numlock",
)  # fmt: skip
FUNCTION_KEYS = tuple(f"f{i}" for i in range(1, 25))
KEY_ALIASES = {
    "control": "ctrl", "cmd": "win", "super": "win", "meta": "win", "return": "enter",
    "escape": "esc", "del": "delete", "ins": "insert", "pgup": "pageup", "pgdn": "pagedown",
    "spacja": "space",
}  # fmt: skip


def parse_hotkey(text: str) -> list[str]:
    """'Ctrl+Shift+C' → ['ctrl', 'shift', 'c']. Znak '+' zapisujemy jako 'plus'."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+")]
    keys: list[str] = []
    for part in parts:
        if not part:
            continue
        name = KEY_ALIASES.get(part, part)
        if not (
            name in MODIFIER_KEYS
            or name in SPECIAL_KEYS
            or name in FUNCTION_KEYS
            or name == "plus"
            or len(name) == 1
            or name.startswith("media_")
        ):
            raise ValueError(f"nieznany klawisz: {part}")
        keys.append(name)
    if not keys:
        raise ValueError("pusty skrót")
    return keys


def format_hotkey(keys: list[str]) -> str:
    pretty = []
    for k in keys:
        if k in MODIFIER_KEYS:
            pretty.append(k.capitalize())
        elif len(k) == 1:
            pretty.append(k.upper())
        else:
            pretty.append(k.upper() if k in FUNCTION_KEYS else k.capitalize())
    return "+".join(pretty)


# --------------------------------------------------------------------------- programy i pliki


@register_action("launch", "Uruchom program", "Uruchamia program lub przełącza na jego okno")
class LaunchAction(ActionBase):
    type: Literal["launch"] = "launch"
    path: str = Field("", title="Program", json_schema_extra={"widget": "exe"})
    args: str = Field("", title="Argumenty")
    cwd: str = Field("", title="Katalog roboczy", json_schema_extra={"widget": "folder"})
    focus_if_running: bool = Field(True, title="Jeśli już działa, przełącz na jego okno")
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        if not self.path:
            raise ValueError("nie podano programu")
        exe_name = self.path.replace("/", "\\").rsplit("\\", 1)[-1]
        if self.focus_if_running and ctx.platform.focus_process(exe_name):
            return
        ctx.platform.launch(self.path, self.args, self.cwd)

    def summary(self) -> str:
        return f"Uruchom {self.path.replace('/', chr(92)).rsplit(chr(92), 1)[-1] or '?'}"


@register_action("open", "Otwórz plik/folder")
class OpenAction(ActionBase):
    type: Literal["open"] = "open"
    path: str = Field("", title="Plik lub folder", json_schema_extra={"widget": "path"})
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        if not self.path:
            raise ValueError("nie podano ścieżki")
        ctx.platform.open_path(self.path)

    def summary(self) -> str:
        return f"Otwórz {self.path}"


@register_action("url", "Otwórz adres WWW")
class UrlAction(ActionBase):
    type: Literal["url"] = "url"
    url: str = Field("https://", title="Adres")
    browser: str = Field(
        "", title="Przeglądarka (puste = domyślna)", json_schema_extra={"widget": "exe"}
    )
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        if not self.url or self.url == "https://":
            raise ValueError("nie podano adresu")
        ctx.platform.open_url(self.url, self.browser)

    def summary(self) -> str:
        return self.url


# --------------------------------------------------------------------------- klawiatura i mysz


@register_action("hotkey", "Skrót klawiszowy", "Kombinacja klawiszy, np. Ctrl+Shift+C, Win+E, F13")
class HotkeyAction(ActionBase):
    type: Literal["hotkey"] = "hotkey"
    keys: str = Field("", title="Skrót", json_schema_extra={"widget": "hotkey"})

    @field_validator("keys")
    @classmethod
    def _check(cls, value: str) -> str:
        if value:
            parse_hotkey(value)
        return value

    def run(self, ctx: ActionContext) -> None:
        if not self.keys:
            raise ValueError("pusty skrót")
        ctx.platform.send_hotkey(parse_hotkey(self.keys))

    def summary(self) -> str:
        return format_hotkey(parse_hotkey(self.keys)) if self.keys else "Skrót"


@register_action("type_text", "Wpisz tekst", "Wpisuje tekst (Unicode, także polskie znaki)")
class TypeTextAction(ActionBase):
    type: Literal["type_text"] = "type_text"
    text: str = Field("", title="Tekst", json_schema_extra={"widget": "multiline"})

    def run(self, ctx: ActionContext) -> None:
        ctx.platform.type_text(self.text)

    def summary(self) -> str:
        short = self.text.replace("\n", " ")
        return f"Wpisz „{short[:20]}”"


MediaName = Literal["play_pause", "next", "prev", "stop", "vol_up", "vol_down", "mute"]
MEDIA_LABELS: dict[str, Any] = {
    "play_pause": "Odtwórz/Pauza",
    "next": "Następny utwór",
    "prev": "Poprzedni utwór",
    "stop": "Stop",
    "vol_up": "Głośniej",
    "vol_down": "Ciszej",
    "mute": "Wycisz",
}


@register_action("media", "Multimedia", "Odtwarzanie i głośność systemu")
class MediaAction(ActionBase):
    type: Literal["media"] = "media"
    key: MediaName = Field(
        "play_pause", title="Klawisz", json_schema_extra={"labels": MEDIA_LABELS}
    )
    step: int = Field(2, ge=1, le=20, title="Krok głośności (%)")
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        platform = ctx.platform
        if self.key in ("vol_up", "vol_down"):
            delta = self.step * ctx.steps * (1 if self.key == "vol_up" else -1)
            value = platform.change_system_volume(delta)
            if value is None:  # brak API głośności – klawisze multimedialne
                for _ in range(ctx.steps):
                    platform.media_key(self.key)
                value = platform.get_system_volume()
            if value is not None:
                ctx.host.show_bar("Glosnosc", value)
            return
        if self.key == "mute":
            muted = platform.toggle_system_mute()
            if muted is None:
                platform.media_key("mute")
            else:
                ctx.host.show_text("Wyciszono" if muted else "Dzwiek wlaczony", ms=1000)
            return
        for _ in range(ctx.steps):
            platform.media_key(self.key)

    def summary(self) -> str:
        return MEDIA_LABELS.get(self.key, self.key)


@register_action("app_volume", "Głośność programu", "Głośność wybranego procesu (mikser Windows)")
class AppVolumeAction(ActionBase):
    type: Literal["app_volume"] = "app_volume"
    process: str = Field(
        "", title="Proces (np. spotify.exe)", json_schema_extra={"widget": "process"}
    )
    mode: Literal["up", "down", "mute"] = Field(
        "up",
        title="Działanie",
        json_schema_extra={"labels": {"up": "Głośniej", "down": "Ciszej", "mute": "Wycisz/włącz"}},
    )
    step: int = Field(5, ge=1, le=50, title="Krok (%)")
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        if not self.process:
            raise ValueError("nie podano procesu")
        name = self.process.rsplit(".", 1)[0][:12]
        if self.mode == "mute":
            muted = ctx.platform.toggle_app_mute(self.process)
            if muted is None:
                ctx.host.show_text(name, "nie gra", ms=1000)
            else:
                ctx.host.show_text(name, "wyciszony" if muted else "dzwiek wlaczony", ms=1000)
            return
        delta = self.step * ctx.steps * (1 if self.mode == "up" else -1)
        value = ctx.platform.change_app_volume(self.process, delta)
        if value is None:
            ctx.host.show_text(name, "nie gra", ms=1000)
        else:
            ctx.host.show_bar(name, value)

    def summary(self) -> str:
        return f"Głośność {self.process or '?'} ({self.mode})"


@register_action("scroll", "Przewijanie")
class ScrollAction(ActionBase):
    type: Literal["scroll"] = "scroll"
    direction: Literal["up", "down", "left", "right"] = Field(
        "down",
        title="Kierunek",
        json_schema_extra={
            "labels": {"up": "W górę", "down": "W dół", "left": "W lewo", "right": "W prawo"}
        },
    )
    lines: int = Field(3, ge=1, le=50, title="Linii na krok")
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        amount = self.lines * ctx.steps
        dx = {"left": -amount, "right": amount}.get(self.direction, 0)
        dy = {"up": amount, "down": -amount}.get(self.direction, 0)
        ctx.platform.scroll(dx, dy)

    def summary(self) -> str:
        return f"Przewiń {self.direction}"


# --------------------------------------------------------------------------- polecenia


@register_action("shell", "Polecenie", "Polecenie cmd lub PowerShell")
class ShellAction(ActionBase):
    type: Literal["shell"] = "shell"
    command: str = Field("", title="Polecenie", json_schema_extra={"widget": "multiline"})
    shell: Literal["cmd", "powershell"] = Field("cmd", title="Powłoka")
    hidden: bool = Field(True, title="Ukryte okno")
    timeout_s: float = Field(30.0, ge=0.5, le=3600, title="Limit czasu (s)")
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        if not self.command.strip():
            raise ValueError("puste polecenie")
        code = ctx.platform.run_shell(self.command, self.shell, self.timeout_s, self.hidden)
        if code != 0:
            log.warning("Polecenie zakończone kodem %s: %s", code, self.command)

    def summary(self) -> str:
        return f"{self.shell}: {self.command[:24]}"


class MacroStep(BaseModel):
    action: Action
    delay_ms: int = Field(0, ge=0, le=60000, title="Opóźnienie po kroku (ms)")


@register_action("macro", "Makro", "Lista kroków wykonywanych po kolei")
class MacroAction(ActionBase):
    type: Literal["macro"] = "macro"
    steps: list[MacroStep] = Field(
        default_factory=list, title="Kroki", json_schema_extra={"widget": "macro"}
    )

    def run(self, ctx: ActionContext) -> None:
        if ctx.depth >= MAX_MACRO_DEPTH:
            raise RecursionError("zbyt głębokie zagnieżdżenie makr")
        for step in self.steps:
            step.action.execute(ctx.child())
            if step.delay_ms:
                time.sleep(step.delay_ms / 1000)

    def summary(self) -> str:
        return f"Makro ({len(self.steps)} kroków)"


# --------------------------------------------------------------------------- profile i system


@register_action("profile", "Zmień profil")
class ProfileAction(ActionBase):
    type: Literal["profile"] = "profile"
    mode: Literal["switch", "next", "prev"] = Field(
        "next",
        title="Działanie",
        json_schema_extra={
            "labels": {"switch": "Przełącz na profil", "next": "Następny", "prev": "Poprzedni"}
        },
    )
    profile: str = Field("", title="Profil", json_schema_extra={"widget": "profile"})

    def run(self, ctx: ActionContext) -> None:
        if self.mode == "next":
            ctx.host.next_profile()
        elif self.mode == "prev":
            ctx.host.prev_profile()
        else:
            if not self.profile:
                raise ValueError("nie wybrano profilu")
            ctx.host.switch_profile(self.profile)

    def summary(self) -> str:
        return {"next": "Następny profil", "prev": "Poprzedni profil"}.get(
            self.mode, f"Profil {self.profile}"
        )


@register_action(
    "layer", "Warstwa (profil na czas trzymania)", "Profil aktywny tylko podczas trzymania klawisza"
)
class LayerAction(ActionBase):
    """Obsługiwana przez kontroler bezpośrednio na zdarzeniach down/up klawisza."""

    type: Literal["layer"] = "layer"
    profile: str = Field("", title="Profil", json_schema_extra={"widget": "profile"})
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        log.debug("Warstwa %s – obsługiwana przez kontroler", self.profile)

    def summary(self) -> str:
        return f"Warstwa {self.profile}"


@register_action("system", "System")
class SystemAction(ActionBase):
    type: Literal["system"] = "system"
    command: Literal["lock", "screen_off"] = Field(
        "lock",
        title="Polecenie",
        json_schema_extra={"labels": {"lock": "Zablokuj komputer", "screen_off": "Wyłącz ekran"}},
    )
    encoder_repeat: ClassVar[bool] = False

    def run(self, ctx: ActionContext) -> None:
        if self.command == "lock":
            ctx.platform.lock_screen()
        else:
            ctx.platform.screen_off()

    def summary(self) -> str:
        return "Zablokuj" if self.command == "lock" else "Wyłącz ekran"


__all__ = [
    "AppVolumeAction",
    "HotkeyAction",
    "LaunchAction",
    "LayerAction",
    "MacroAction",
    "MacroStep",
    "MediaAction",
    "OpenAction",
    "PlatformError",
    "ProfileAction",
    "ScrollAction",
    "ShellAction",
    "SystemAction",
    "TypeTextAction",
    "UrlAction",
    "format_hotkey",
    "parse_hotkey",
]
