from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tap32.core.actions import UnknownAction, make_action
from tap32.core.actions.builtin import HotkeyAction, LaunchAction, MacroAction
from tap32.core.config import (
    CURRENT_SCHEMA,
    Config,
    ConfigStore,
    KeyBinding,
    Profile,
    duplicate_profile,
    export_profile,
    import_profile,
    migrate,
)
from tap32.core.defaults import default_profiles


def test_default_config_is_valid() -> None:
    config = Config()
    config.ensure_valid()
    assert config.default_profile == "Domyślny"
    profile = config.profile("Domyślny")
    assert profile is not None
    assert len(profile.keys) == 10
    assert isinstance(profile.keys[1].tap, LaunchAction)
    assert profile.keys[1].tap.path == "calc.exe"
    assert all(len(label) <= 7 for label in profile.labels())


def test_roundtrip_preserves_action_types() -> None:
    config = Config(profiles=default_profiles())
    config.profiles[0].keys[2].hold = make_action(
        "macro",
        steps=[
            {"action": {"type": "hotkey", "keys": "ctrl+a"}, "delay_ms": 50},
            {"action": {"type": "type_text", "text": "Zażółć"}},
        ],
    )
    data = json.loads(config.model_dump_json())
    assert data["profiles"][0]["keys"]["2"]["hold"]["steps"][0]["action"]["keys"] == "ctrl+a"
    back = Config.model_validate(data)
    macro = back.profiles[0].keys[2].hold
    assert isinstance(macro, MacroAction)
    assert isinstance(macro.steps[0].action, HotkeyAction)
    assert macro.steps[1].action.text == "Zażółć"  # type: ignore[attr-defined]


def test_unknown_action_type_is_preserved() -> None:
    raw = {"type": "teleport", "target": "Mars"}
    binding = KeyBinding.model_validate({"tap": raw})
    assert isinstance(binding.tap, UnknownAction)
    assert binding.model_dump(mode="json")["tap"] == raw


def test_invalid_hotkey_rejected() -> None:
    with pytest.raises(ValidationError):
        KeyBinding.model_validate({"tap": {"type": "hotkey", "keys": "ctrl+nonsense"}})


def test_missing_keys_are_filled() -> None:
    profile = Profile.model_validate({"name": "X", "keys": {"3": {"label": "A"}}})
    assert sorted(profile.keys) == list(range(1, 11))
    assert profile.keys[3].label == "A"


def test_migration_from_schema_1() -> None:
    v1 = {
        "version": 1,
        "hold_ms": 700,
        "profiles": [
            {
                "name": "Stary",
                "keys": [{"label": "A", "tap": {"type": "hotkey", "keys": "ctrl+c"}}, None],
                "auto_processes": ["game.exe"],
            }
        ],
    }
    data = migrate(v1)
    assert data["schema_version"] == CURRENT_SCHEMA
    config = Config.model_validate(data)
    assert config.settings.gestures.hold_ms == 700
    assert config.profiles[0].keys[1].label == "A"
    assert config.profiles[0].processes == ["game.exe"]


def test_store_save_load_backup(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    config = store.load()  # brak pliku → domyślna
    assert config.profiles
    config.settings.device.brightness = 77
    store.save(config)
    assert not store.backup_path.exists()
    config.settings.device.brightness = 88
    store.save(config)
    assert store.backup_path.exists()
    assert (
        json.loads(store.backup_path.read_text("utf-8"))["settings"]["device"]["brightness"] == 77
    )
    assert store.load().settings.device.brightness == 88


def test_store_corrupted_falls_back_to_backup(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    config = store.load()
    config.settings.device.brightness = 55
    store.save(config)
    store.save(config)  # powstaje .bak z jasnością 55
    store.path.write_text("{ to nie jest json", encoding="utf-8")
    loaded = store.load()
    assert loaded.settings.device.brightness == 55
    assert (tmp_path / "config.broken.json").exists()


def test_atomic_write_leaves_no_temp(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    store.save(store.load())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.json"]


def test_export_import_profile(tmp_path: Path) -> None:
    config = Config(profiles=default_profiles())
    config.ensure_valid()
    path = tmp_path / "p.json"
    export_profile(config.profiles[0], path)
    imported = import_profile(path, config)
    assert imported.name == "Domyślny (2)"
    assert imported.id != config.profiles[0].id
    assert isinstance(imported.keys[1].tap, LaunchAction)

    (tmp_path / "bad.json").write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        import_profile(tmp_path / "bad.json", config)


def test_duplicate_profile_is_deep_copy() -> None:
    config = Config(profiles=default_profiles())
    copy = duplicate_profile(config.profiles[0], config)
    copy.keys[1].label = "Zmiana"
    assert config.profiles[0].keys[1].label == "Kalk"
    assert copy.name == "Domyślny – kopia"
