"""Wyliczanie skrótów HID trybu awaryjnego z profilu i ustawień."""

from __future__ import annotations

from .actions import ActionBase, parse_hotkey
from .actions.builtin import FUNCTION_KEYS, HotkeyAction, MediaAction
from .config import FallbackSettings, Profile
from .protocol import FallbackBinding

# Klawisze, które firmware zna po nazwie (docs/PROTOCOL.md, set_fallback.code).
_HID_SPECIAL = {
    "enter", "esc", "backspace", "tab", "space", "capslock", "printscreen", "scrolllock",
    "pause", "insert", "home", "pageup", "delete", "end", "pagedown", "right", "left", "down",
    "up", "numlock", "menu",
}  # fmt: skip
_HID_PUNCT = set("-=[]\\;'`,./")
_MODS = {"ctrl", "shift", "alt", "win"}
_MEDIA = {"play_pause", "next", "prev", "stop", "vol_up", "vol_down", "mute"}

DEFAULTS = {
    "10": FallbackBinding(10, media="mute"),
    "enc_cw": FallbackBinding("enc_cw", media="vol_up"),
    "enc_ccw": FallbackBinding("enc_ccw", media="vol_down"),
}


def binding_from_action(slot: int | str, action: ActionBase | None) -> FallbackBinding | None:
    """Zamienia akcję hotkey/media na skrót HID; inne typy nie mają odpowiednika."""
    if isinstance(action, MediaAction) and action.key in _MEDIA:
        return FallbackBinding(slot, media=action.key)
    if isinstance(action, HotkeyAction) and action.keys:
        try:
            keys = parse_hotkey(action.keys)
        except ValueError:
            return None
        mods = tuple(k for k in keys if k in _MODS)
        rest = [k for k in keys if k not in _MODS]
        if len(rest) > 1:
            return None  # HID: jeden zwykły klawisz na skrót
        code: str | None = None
        if rest:
            key = rest[0]
            if len(key) == 1 and (key.isalnum() or key in _HID_PUNCT):
                code = key.lower()
            elif key in FUNCTION_KEYS or key in _HID_SPECIAL:
                code = key
            else:
                return None
        if not mods and code is None:
            return None
        return FallbackBinding(slot, mods=mods, code=code)
    return None


def compute_fallback(profile: Profile | None, settings: FallbackSettings) -> list[FallbackBinding]:
    slots: dict[str, FallbackBinding] = dict(DEFAULTS)
    if settings.from_profile and profile is not None:
        for key in range(1, 11):
            binding = binding_from_action(key, profile.keys[key].tap)
            if binding is not None:
                slots[str(key)] = binding
        for slot, gesture in (("enc_cw", "rotate_cw"), ("enc_ccw", "rotate_ccw")):
            binding = binding_from_action(slot, profile.encoder.action_for(gesture))
            if binding is not None:
                slots[slot] = binding
    for entry in settings.custom:
        slot_value: int | str = int(entry.slot) if entry.slot.isdigit() else entry.slot
        slots[entry.slot] = FallbackBinding(
            slot_value, mods=tuple(entry.mods), code=entry.code, media=entry.media
        )
    order = [str(i) for i in range(1, 11)] + ["enc_cw", "enc_ccw"]
    return [slots[s] for s in order if s in slots]
