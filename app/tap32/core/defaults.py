"""Domyślne profile tworzone przy pierwszym uruchomieniu."""

from __future__ import annotations

from .actions import make_action
from .config import EncoderBinding, KeyBinding, Profile


def default_profile() -> Profile:
    keys = {
        1: KeyBinding(label="Kalk", color="#2e7d32", tap=make_action("launch", path="calc.exe")),
        2: KeyBinding(
            label="Notatn", color="#1565c0", tap=make_action("launch", path="notepad.exe")
        ),
        3: KeyBinding(
            label="Pliki",
            color="#ef6c00",
            tap=make_action("launch", path="explorer.exe", focus_if_running=False),
        ),
        4: KeyBinding(
            label="WWW", color="#6a1b9a", tap=make_action("url", url="https://www.google.com")
        ),
        5: KeyBinding(label="Kopiuj", color="#37474f", tap=make_action("hotkey", keys="ctrl+c")),
        6: KeyBinding(label="Wklej", color="#37474f", tap=make_action("hotkey", keys="ctrl+v")),
        7: KeyBinding(label="Play", color="#c62828", tap=make_action("media", key="play_pause")),
        8: KeyBinding(label="< Prof", color="#00838f", tap=make_action("profile", mode="prev")),
        9: KeyBinding(label="Prof >", color="#00838f", tap=make_action("profile", mode="next")),
        10: KeyBinding(label="Wycisz", tap=make_action("media", key="mute")),
    }
    encoder = EncoderBinding(
        rotate_cw=make_action("media", key="vol_up"),
        rotate_ccw=make_action("media", key="vol_down"),
        press_rotate_cw=make_action("media", key="next"),
        press_rotate_ccw=make_action("media", key="prev"),
    )
    return Profile(name="Domyślny", keys=keys, encoder=encoder)


def stream_profile() -> Profile:
    """Przykład automatycznego przełączania: OBS (skróty F13–F21 do przypisania w OBS)."""
    keys = {
        i: KeyBinding(
            label=f"Scena {i}", color="#4527a0", tap=make_action("hotkey", keys=f"f{12 + i}")
        )
        for i in range(1, 7)
    }
    keys[7] = KeyBinding(label="Mic", color="#c62828", tap=make_action("hotkey", keys="f19"))
    keys[8] = KeyBinding(label="REC", color="#b71c1c", tap=make_action("hotkey", keys="f20"))
    keys[9] = KeyBinding(label="LIVE", color="#b71c1c", hold=make_action("hotkey", keys="f21"))
    keys[10] = KeyBinding(label="Wycisz", tap=make_action("media", key="mute"))
    encoder = EncoderBinding(
        rotate_cw=make_action("media", key="vol_up"),
        rotate_ccw=make_action("media", key="vol_down"),
    )
    return Profile(name="Stream", keys=keys, encoder=encoder, processes=["obs64.exe"])


def default_profiles() -> list[Profile]:
    return [default_profile(), stream_profile()]
