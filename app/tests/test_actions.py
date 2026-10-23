from __future__ import annotations

import pytest

from tap32.core.actions import (
    ACTION_TYPES,
    ActionBase,
    ActionContext,
    ActionExecutor,
    format_hotkey,
    make_action,
    parse_hotkey,
    register_action,
)
from tap32.core.actions.builtin import MAX_MACRO_DEPTH
from tests.conftest import FakeHost, FakePlatform


def ctx(platform: FakePlatform, host: FakeHost, steps: int = 1) -> ActionContext:
    return ActionContext(platform, host, steps=steps, key=1)


def test_registry_contains_all_types() -> None:
    expected = {
        "launch", "open", "url", "hotkey", "type_text", "media", "app_volume", "scroll",
        "shell", "macro", "profile", "layer", "system",
    }  # fmt: skip
    assert expected <= set(ACTION_TYPES)
    assert all(cls.label for cls in ACTION_TYPES.values())


def test_parse_and_format_hotkey() -> None:
    assert parse_hotkey("Ctrl+Shift+C") == ["ctrl", "shift", "c"]
    assert parse_hotkey("win + e") == ["win", "e"]
    assert parse_hotkey("F13") == ["f13"]
    assert parse_hotkey("control+plus") == ["ctrl", "plus"]
    assert format_hotkey(["ctrl", "alt", "delete"]) == "Ctrl+Alt+Delete"
    with pytest.raises(ValueError):
        parse_hotkey("ctrl+banana")
    with pytest.raises(ValueError):
        parse_hotkey("")


def test_launch_focuses_running(platform: FakePlatform, host: FakeHost) -> None:
    action = make_action("launch", path=r"C:\Program Files\App\app.exe", args="-x")
    action.execute(ctx(platform, host))
    assert platform.calls == [("launch", r"C:\Program Files\App\app.exe", "-x", "")]
    platform.calls.clear()
    platform.running.add("app.exe")
    action.execute(ctx(platform, host))
    assert platform.calls == [("focus", "app.exe")]


def test_launch_without_focus_option(platform: FakePlatform, host: FakeHost) -> None:
    platform.running.add("explorer.exe")
    make_action("launch", path="explorer.exe", focus_if_running=False).execute(ctx(platform, host))
    assert platform.calls == [("launch", "explorer.exe", "", "")]


def test_hotkey_repeats_per_encoder_step(platform: FakePlatform, host: FakeHost) -> None:
    make_action("hotkey", keys="ctrl+plus").execute(ctx(platform, host, steps=3))
    assert platform.calls == [("hotkey", ("ctrl", "plus"))] * 3


def test_type_text_unicode(platform: FakePlatform, host: FakeHost) -> None:
    make_action("type_text", text="Zażółć gęślą jaźń").execute(ctx(platform, host))
    assert platform.calls == [("type", "Zażółć gęślą jaźń")]


def test_media_volume_steps_and_bar(platform: FakePlatform, host: FakeHost) -> None:
    make_action("media", key="vol_up", step=2).execute(ctx(platform, host, steps=3))
    assert platform.calls == [("volume", 6)]
    assert host.calls == [("bar", "Glosnosc", 56)]


def test_media_play_pause(platform: FakePlatform, host: FakeHost) -> None:
    make_action("media", key="play_pause").execute(ctx(platform, host))
    assert platform.calls == [("media", "play_pause")]


def test_media_mute_shows_text(platform: FakePlatform, host: FakeHost) -> None:
    make_action("media", key="mute").execute(ctx(platform, host))
    assert platform.calls == [("mute", True)]
    assert host.calls[0][0] == "text"


def test_app_volume(platform: FakePlatform, host: FakeHost) -> None:
    make_action("app_volume", process="spotify.exe", mode="down", step=5).execute(
        ctx(platform, host, steps=2)
    )
    assert platform.app_volumes["spotify.exe"] == 30
    assert host.calls == [("bar", "spotify", 30)]
    make_action("app_volume", process="nothing.exe", mode="up").execute(ctx(platform, host))
    assert host.calls[-1] == ("text", "nothing", "nie gra")


def test_scroll(platform: FakePlatform, host: FakeHost) -> None:
    make_action("scroll", direction="down", lines=2).execute(ctx(platform, host, steps=3))
    make_action("scroll", direction="left", lines=1).execute(ctx(platform, host))
    assert platform.calls == [("scroll", 0, -6), ("scroll", -1, 0)]


def test_shell_and_system(platform: FakePlatform, host: FakeHost) -> None:
    make_action("shell", command="echo hi", shell="powershell").execute(ctx(platform, host))
    make_action("system", command="lock").execute(ctx(platform, host))
    make_action("system", command="screen_off").execute(ctx(platform, host))
    assert platform.calls == [("shell", "echo hi", "powershell"), ("lock",), ("screen_off",)]


def test_profile_actions(platform: FakePlatform, host: FakeHost) -> None:
    make_action("profile", mode="next").execute(ctx(platform, host))
    make_action("profile", mode="prev").execute(ctx(platform, host))
    make_action("profile", mode="switch", profile="Stream").execute(ctx(platform, host))
    assert host.calls == [("next",), ("prev",), ("switch", "Stream")]


def test_macro_runs_steps_in_order(platform: FakePlatform, host: FakeHost) -> None:
    macro = make_action(
        "macro",
        steps=[
            {"action": {"type": "hotkey", "keys": "win+r"}, "delay_ms": 1},
            {"action": {"type": "type_text", "text": "notepad"}},
            {"action": {"type": "hotkey", "keys": "enter"}},
        ],
    )
    macro.execute(ctx(platform, host))
    assert platform.calls == [
        ("hotkey", ("win", "r")),
        ("type", "notepad"),
        ("hotkey", ("enter",)),
    ]


def test_macro_recursion_limit(platform: FakePlatform, host: FakeHost) -> None:
    inner: dict = {"type": "hotkey", "keys": "a"}
    for _ in range(MAX_MACRO_DEPTH + 1):
        inner = {"type": "macro", "steps": [{"action": inner}]}
    with pytest.raises(RecursionError):
        make_action("macro", **{k: v for k, v in inner.items() if k != "type"}).execute(
            ctx(platform, host)
        )


def test_executor_logs_errors_and_continues(
    platform: FakePlatform, host: FakeHost, caplog: pytest.LogCaptureFixture
) -> None:
    executor = ActionExecutor(synchronous=True)
    results: list[BaseException | None] = []
    executor.submit(
        make_action("launch", path=""), ctx(platform, host), lambda a, c, e: results.append(e)
    )
    executor.submit(
        make_action("hotkey", keys="a"), ctx(platform, host), lambda a, c, e: results.append(e)
    )
    assert isinstance(results[0], ValueError)
    assert results[1] is None
    assert "nie powiodła się" in caplog.text


def test_executor_threaded(platform: FakePlatform, host: FakeHost) -> None:
    executor = ActionExecutor(workers=2)
    future = executor.submit(make_action("hotkey", keys="b"), ctx(platform, host))
    assert future is not None
    future.result(timeout=5)
    executor.shutdown()
    assert platform.calls == [("hotkey", ("b",))]


def test_custom_action_type_can_be_registered(platform: FakePlatform, host: FakeHost) -> None:
    from typing import Literal

    @register_action("test_beep", "Test")
    class Beep(ActionBase):
        type: Literal["test_beep"] = "test_beep"
        times: int = 1

        def run(self, ctx: ActionContext) -> None:
            ctx.platform.calls.append(("beep", self.times))  # type: ignore[attr-defined]

    try:
        action = make_action("test_beep", times=2)
        action.execute(ctx(platform, host, steps=2))
        assert platform.calls == [("beep", 2), ("beep", 2)]
    finally:
        del ACTION_TYPES["test_beep"]
