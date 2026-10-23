"""Konfiguracja Tap32: modele pydantic, migracje schematu, zapis atomowy, import/eksport."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .actions import Action, ActionBase
from .gestures import Gesture
from .protocol import KEY_COUNT

log = logging.getLogger("tap32.config")

CURRENT_SCHEMA = 2
APP_DIR_NAME = "Tap32"
CONFIG_FILE = "config.json"


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)


# --------------------------------------------------------------------------- profile


class KeyBinding(Model):
    label: str = ""
    color: str = "#3c4a5c"
    tap: Action | None = None
    hold: Action | None = None
    double_tap: Action | None = None

    def action_for(self, gesture: Gesture | str) -> ActionBase | None:
        name = str(gesture)
        if name not in ("tap", "hold", "double_tap"):
            return None
        action: ActionBase | None = getattr(self, name)
        return action

    def set_action(self, gesture: Gesture | str, action: ActionBase | None) -> None:
        setattr(self, str(gesture), action)

    def actions(self) -> list[ActionBase]:
        return [a for a in (self.tap, self.hold, self.double_tap) if a is not None]


class EncoderBinding(Model):
    rotate_cw: Action | None = None
    rotate_ccw: Action | None = None
    press_rotate_cw: Action | None = None
    press_rotate_ccw: Action | None = None

    def action_for(self, gesture: Gesture | str) -> ActionBase | None:
        return getattr(self, str(gesture), None)

    def set_action(self, gesture: Gesture | str, action: ActionBase | None) -> None:
        setattr(self, str(gesture), action)


def _empty_keys() -> dict[int, KeyBinding]:
    return {k: KeyBinding() for k in range(1, KEY_COUNT + 1)}


class Profile(Model):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Profil"
    keys: dict[int, KeyBinding] = Field(default_factory=_empty_keys)
    encoder: EncoderBinding = Field(default_factory=lambda: EncoderBinding())
    processes: list[str] = Field(default_factory=list)  # automatyczne przełączanie

    @field_validator("keys")
    @classmethod
    def _fill_keys(cls, keys: dict[int, KeyBinding]) -> dict[int, KeyBinding]:
        filled = {k: keys.get(k, KeyBinding()) for k in range(1, KEY_COUNT + 1)}
        return filled

    @field_validator("processes")
    @classmethod
    def _normalize_processes(cls, items: list[str]) -> list[str]:
        return [p.strip() for p in items if p.strip()]

    def key(self, number: int) -> KeyBinding:
        return self.keys[number]

    def labels(self) -> list[str]:
        return [self.keys[k].label for k in range(1, 10)]

    def action_for(self, key: int | None, gesture: Gesture) -> ActionBase | None:
        if gesture in (
            Gesture.ROTATE_CW, Gesture.ROTATE_CCW, Gesture.PRESS_ROTATE_CW, Gesture.PRESS_ROTATE_CCW
        ):  # fmt: skip
            return self.encoder.action_for(gesture)
        if key is None:
            return None
        return self.keys[key].action_for(gesture)

    def matches_process(self, exe: str) -> bool:
        exe = exe.lower()
        return any(p.lower() == exe for p in self.processes)


# --------------------------------------------------------------------------- ustawienia


class DeviceSettings(Model):
    port: str = "auto"
    brightness: int = Field(128, ge=0, le=255)
    screensaver_s: int = Field(300, ge=0, le=65535)
    display_mode: Literal["grid", "profile"] = "grid"
    flip: bool = False
    enc_reverse: bool = False
    enc_pulses: int = Field(4, ge=1, le=8)
    debounce_ms: int = Field(8, ge=1, le=50)


class GestureSettings(Model):
    hold_ms: int = Field(500, ge=100, le=5000)
    double_tap_ms: int = Field(300, ge=100, le=2000)
    hold_on_threshold: bool = False


class EncoderSettings(Model):
    accel_enabled: bool = False
    accel_window_ms: int = Field(40, ge=5, le=500)
    accel_multiplier: int = Field(3, ge=1, le=10)


FallbackSlot = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "enc_cw", "enc_ccw"]


class FallbackEntry(Model):
    slot: FallbackSlot
    mods: list[str] = Field(default_factory=list)
    code: str | None = None
    media: str | None = None


class FallbackSettings(Model):
    from_profile: bool = True  # wyliczaj skróty z aktywnego profilu (hotkey/media)
    custom: list[FallbackEntry] = Field(default_factory=list)  # nadpisania


class AppSettings(Model):
    autostart: bool = False
    start_minimized: bool = False
    theme: Literal["system", "light", "dark"] = "system"
    flash_on_action: bool = True
    auto_switch: bool = True


class Settings(Model):
    device: DeviceSettings = Field(default_factory=lambda: DeviceSettings())
    gestures: GestureSettings = Field(default_factory=lambda: GestureSettings())
    encoder: EncoderSettings = Field(default_factory=lambda: EncoderSettings())
    fallback: FallbackSettings = Field(default_factory=lambda: FallbackSettings())
    app: AppSettings = Field(default_factory=lambda: AppSettings())


class Config(Model):
    schema_version: int = CURRENT_SCHEMA
    settings: Settings = Field(default_factory=lambda: Settings())
    profiles: list[Profile] = Field(default_factory=list)
    default_profile: str = ""

    def profile(self, name: str) -> Profile | None:
        for p in self.profiles:
            if p.name == name:
                return p
        return None

    def profile_names(self) -> list[str]:
        return [p.name for p in self.profiles]

    def unique_name(self, base: str) -> str:
        names = set(self.profile_names())
        if base not in names:
            return base
        i = 2
        while f"{base} ({i})" in names:
            i += 1
        return f"{base} ({i})"

    def ensure_valid(self) -> None:
        """Gwarantuje co najmniej jeden profil i poprawny profil domyślny."""
        if not self.profiles:
            from .defaults import default_profiles

            self.profiles = default_profiles()
        if self.profile(self.default_profile) is None:
            self.default_profile = self.profiles[0].name


# --------------------------------------------------------------------------- migracje


def _migrate_1_to_2(data: dict[str, Any]) -> dict[str, Any]:
    """Schemat 1: klawisze jako lista, progi gestów w korzeniu, `auto_processes`."""
    settings = data.setdefault("settings", {})
    gestures = settings.setdefault("gestures", {})
    for old, new in (("hold_ms", "hold_ms"), ("double_tap_ms", "double_tap_ms")):
        if old in data:
            gestures[new] = data.pop(old)
    for profile in data.get("profiles", []):
        keys = profile.get("keys")
        if isinstance(keys, list):
            profile["keys"] = {str(i + 1): k for i, k in enumerate(keys) if k is not None}
        if "auto_processes" in profile:
            profile["processes"] = profile.pop("auto_processes")
    data.pop("version", None)
    data["schema_version"] = 2
    return data


MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _migrate_1_to_2}


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("schema_version", data.get("version", CURRENT_SCHEMA))
    if not isinstance(version, int):
        raise ValueError("bad schema_version")
    if version > CURRENT_SCHEMA:
        log.warning("Konfiguracja z nowszej wersji (%s) – wczytuję w miarę możliwości", version)
        return data
    while version < CURRENT_SCHEMA:
        step = MIGRATIONS.get(version)
        if step is None:
            raise ValueError(f"brak migracji ze schematu {version}")
        log.info("Migracja konfiguracji: %s → %s", version, version + 1)
        data = step(data)
        version = data["schema_version"]
    return data


# --------------------------------------------------------------------------- zapis i odczyt


def default_config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME.lower()


def atomic_write(path: Path, text: str) -> None:
    """Zapis przez plik tymczasowy i os.replace (brak uszkodzonego pliku przy awarii)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class ConfigStore:
    """Plik config.json z kopią zapasową poprzedniej wersji (config.json.bak)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_dir() / CONFIG_FILE
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self._lock = threading.Lock()

    def load(self) -> Config:
        if not self.path.exists():
            log.info("Brak konfiguracji – tworzę domyślną (%s)", self.path)
            config = Config()
            config.ensure_valid()
            return config
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("object expected")
            config = Config.model_validate(migrate(data))
        except (OSError, ValueError, ValidationError) as exc:
            log.error("Uszkodzona konfiguracja (%s) – wczytuję kopię zapasową", exc)
            config = self._load_backup()
            broken = self.path.with_suffix(".broken.json")
            try:
                shutil.copy2(self.path, broken)
            except OSError:
                pass
        config.ensure_valid()
        return config

    def _load_backup(self) -> Config:
        try:
            data = json.loads(self.backup_path.read_text(encoding="utf-8"))
            return Config.model_validate(migrate(data))
        except (OSError, ValueError, ValidationError):
            return Config()

    def save(self, config: Config) -> None:
        with self._lock:
            text = config.model_dump_json(indent=2)
            if self.path.exists():
                try:
                    shutil.copy2(self.path, self.backup_path)
                except OSError as exc:
                    log.warning("Nie udało się zrobić kopii zapasowej: %s", exc)
            atomic_write(self.path, text)


# --------------------------------------------------------------------------- import/eksport

EXPORT_FORMAT = "tap32-profile"


def export_profile(profile: Profile, path: Path) -> None:
    payload = {
        "format": EXPORT_FORMAT,
        "schema_version": CURRENT_SCHEMA,
        "profile": profile.model_dump(mode="json"),
    }
    atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False))


def import_profile(path: Path, config: Config) -> Profile:
    """Wczytuje profil z pliku; przy konflikcie nazwy dodaje sufiks. Nie dodaje do config."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("format") == EXPORT_FORMAT:
        raw = data["profile"]
        version = data.get("schema_version", CURRENT_SCHEMA)
        if version < CURRENT_SCHEMA:
            raw = migrate({"schema_version": version, "profiles": [raw]})["profiles"][0]
    elif isinstance(data, dict) and "keys" in data:
        raw = data  # sam profil
    else:
        raise ValueError("To nie jest plik profilu Tap32")
    profile = Profile.model_validate(raw)
    profile.id = uuid.uuid4().hex[:12]
    profile.name = config.unique_name(profile.name)
    return profile


def duplicate_profile(profile: Profile, config: Config) -> Profile:
    copy = Profile.model_validate(profile.model_dump(mode="json"))
    copy.id = uuid.uuid4().hex[:12]
    copy.name = config.unique_name(f"{profile.name} – kopia")
    return copy


__all__ = [
    "CURRENT_SCHEMA",
    "AppSettings",
    "Config",
    "ConfigStore",
    "DeviceSettings",
    "EncoderBinding",
    "EncoderSettings",
    "FallbackEntry",
    "FallbackSettings",
    "GestureSettings",
    "KeyBinding",
    "Profile",
    "Settings",
    "atomic_write",
    "default_config_dir",
    "duplicate_profile",
    "export_profile",
    "import_profile",
    "migrate",
]
