from __future__ import annotations

from tap32.core.actions import make_action
from tap32.core.config import Config, Profile
from tap32.core.defaults import default_profiles
from tap32.core.profiles import ForegroundWatcher, ProfileManager


def make_manager() -> tuple[ProfileManager, list[tuple[str, str]]]:
    config = Config(profiles=[*default_profiles(), Profile(name="Gry", processes=["Game.exe"])])
    config.ensure_valid()
    manager = ProfileManager(config)
    changes: list[tuple[str, str]] = []
    manager.add_listener(lambda p, reason: changes.append((p.name, reason)))
    return manager, changes


def test_next_prev_wraps() -> None:
    manager, changes = make_manager()
    assert manager.active.name == "Domyślny"
    manager.next()
    manager.next()
    manager.next()
    assert manager.active.name == "Domyślny"
    manager.prev()
    assert manager.active.name == "Gry"
    assert [c[1] for c in changes] == ["manual"] * 4


def test_set_active_unknown() -> None:
    manager, _ = make_manager()
    assert not manager.set_active("Nie ma")
    assert manager.active.name == "Domyślny"


def test_auto_switch_and_return() -> None:
    manager, changes = make_manager()
    manager.on_foreground("obs64.exe")
    assert manager.active.name == "Stream"
    assert manager.is_auto
    manager.on_foreground("obs64.exe")  # ten sam proces – bez zmian
    manager.on_foreground("game.EXE")  # wielkość liter bez znaczenia
    assert manager.active.name == "Gry"
    manager.on_foreground("notepad.exe")
    assert manager.active.name == "Domyślny"
    assert not manager.is_auto
    assert changes == [("Stream", "auto"), ("Gry", "auto"), ("Domyślny", "auto-return")]


def test_auto_switch_returns_to_manual_choice() -> None:
    manager, _ = make_manager()
    manager.set_active("Gry")
    manager.on_foreground("obs64.exe")
    manager.on_foreground("explorer.exe")
    assert manager.active.name == "Gry"


def test_auto_switch_disabled() -> None:
    manager, _ = make_manager()
    manager.config.settings.app.auto_switch = False
    manager.on_foreground("obs64.exe")
    assert manager.active.name == "Domyślny"


def test_manual_change_while_auto() -> None:
    manager, _ = make_manager()
    manager.on_foreground("obs64.exe")
    manager.set_active("Gry")
    manager.on_foreground("notepad.exe")  # ręczny wybór nie jest cofany
    assert manager.active.name == "Gry"


def test_layers() -> None:
    manager, changes = make_manager()
    manager.push_layer(5, "Stream")
    assert manager.effective.name == "Stream"
    assert manager.active.name == "Domyślny"
    manager.push_layer(6, "Gry")
    assert manager.effective.name == "Gry"
    manager.pop_layer(6)
    assert manager.effective.name == "Stream"
    manager.pop_layer(5)
    assert manager.effective.name == "Domyślny"
    manager.pop_layer(5)  # ponowne zdjęcie – bez powiadomienia
    assert [c[1] for c in changes] == ["layer"] * 4


def test_rename_updates_references() -> None:
    manager, _ = make_manager()
    config = manager.config
    default = config.profile("Domyślny")
    assert default is not None
    default.keys[4].tap = make_action("profile", mode="switch", profile="Stream")
    default.keys[5].hold = make_action(
        "macro", steps=[{"action": {"type": "layer", "profile": "Stream"}}]
    )
    manager.set_active("Stream")
    manager.rename("Stream", "OBS")
    assert config.profile("OBS") is not None
    assert default.keys[4].tap.profile == "OBS"  # type: ignore[union-attr]
    assert default.keys[5].hold.steps[0].action.profile == "OBS"  # type: ignore[union-attr]
    assert manager.active.name == "OBS"


def test_refresh_after_delete() -> None:
    manager, _ = make_manager()
    manager.set_active("Gry")
    manager.config.profiles = [p for p in manager.config.profiles if p.name != "Gry"]
    manager.refresh()
    assert manager.active.name == "Domyślny"


def test_foreground_watcher_poll() -> None:
    seen: list[str | None] = []
    values = iter(["a.exe", "a.exe", "b.exe"])
    watcher = ForegroundWatcher(lambda: next(values), seen.append)
    watcher.poll_once()
    watcher.poll_once()
    watcher.poll_once()
    assert seen == ["a.exe", "b.exe"]
