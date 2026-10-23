# ruff: noqa: E501
"""Tłumaczenie interfejsu PL → EN.

Teksty w kodzie są po polsku; tr() zwraca angielski odpowiednik, gdy wybrano język „en”.
Brak wpisu w słowniku = tekst bez zmian (np. nazwy własne).
"""

from __future__ import annotations

from ..core.actions import ActionBase, format_hotkey, parse_hotkey

_language = "pl"

EN: dict[str, str] = {
    # nawigacja i okno główne
    "Konfiguracja": "Configuration",
    "Dziennik": "Log",
    "Ustawienia": "Settings",
    "Ustawienia…": "Settings…",
    "Profile": "Profiles",
    "Profil": "Profile",
    "Nowy profil": "New profile",
    "Importuj profil…": "Import profile…",
    "Eksportuj profil…": "Export profile…",
    "Importuj profil": "Import profile",
    "Eksportuj profil": "Export profile",
    "Zamknij okno (działa w tle)": "Close window (keep running in background)",
    "O programie": "About",
    "Zakończ": "Quit",
    "Menu aplikacji": "App menu",
    "Menu urządzenia": "Device menu",
    "Język": "Language",
    "Połączono": "Connected",
    "Rozłączono": "Disconnected",
    "Szukam Tap32…": "Looking for Tap32…",
    "Płytka": "Board",
    "Aktywny profil": "Active profile",
    "Tryb testu sprzętu": "Hardware test mode",
    "Wyślij ponownie ekran i ustawienia": "Resend display and settings",
    "Restart urządzenia": "Restart device",
    "Tryb wgrywania firmware…": "Firmware upload mode…",
    "Tryb wgrywania firmware": "Firmware upload mode",
    "domyślny": "default",
    "Aktywny": "Active",
    "Domyślny": "Default",
    "Ustaw jako aktywny": "Set as active",
    "Właściwości profilu": "Profile properties",
    "Więcej akcji profilu": "More profile actions",
    "Dodaj": "Add",
    "Duplikuj": "Duplicate",
    "Zmień nazwę": "Rename",
    "Eksportuj…": "Export…",
    "Usuń": "Delete",
    "Akcje włączone": "Actions on",
    "Akcje wstrzymane": "Actions paused",
    "Akcje wstrzymane.": "Actions paused.",
    "Naciśnięcia klawiszy nie wykonują akcji.": "Key presses do not run any actions.",
    "Wznów": "Resume",
    "Naciśnięcia tylko podświetlają elementy na podglądzie.": "Presses only highlight items in the preview.",
    "Wyłącz": "Turn off",
    "Kliknij klawisz lub pokrętło, aby edytować akcje. Fizyczne naciśnięcia podświetlają elementy na żywo.": "Click a key or the knob to edit its actions. Physical presses highlight items live.",
    "Automatycznie dla:": "Automatic for:",
    "Nazwa profilu:": "Profile name:",
    "Nowa nazwa:": "New name:",
    "Profil „{name}” już istnieje.": "Profile “{name}” already exists.",
    "Musi zostać co najmniej jeden profil.": "At least one profile must remain.",
    "Usunąć profil „{name}”?": "Delete profile “{name}”?",
    "Profil Tap32 (*.json)": "Tap32 profile (*.json)",
    "Nie udało się zaimportować profilu:": "Could not import the profile:",
    "Nie udało się zapisać:": "Could not save:",
    "Przełączyć urządzenie w tryb wgrywania firmware?\nKB2040 pojawi się jako dysk RPI-RP2, XIAO ESP32-S3 – jako port pobierania.": "Switch the device to firmware upload mode?\nKB2040 will appear as an RPI-RP2 drive, XIAO ESP32-S3 as a download port.",
    "Macropad 3×3 z pokrętłem i ekranem OLED.": "3×3 macropad with a knob and an OLED display.",
    "Ekran nie odpowiada na I²C – szczegóły w zakładce Dziennik": "The display does not respond on I²C – see the Log page for details",
    "Błąd": "Error",
    # podgląd urządzenia
    "Ekran OLED": "OLED display",
    "Siatka etykiet 3×3": "3×3 label grid",
    "Duża nazwa profilu": "Large profile name",
    "Klawisz": "Key",
    "Pokrętło": "Knob",
    "Pokrętło (obrót, przycisk = klawisz 10)": "Knob (rotation, button = key 10)",
    "Pokrętło – przycisk:": "Knob – button:",
    # edytory
    "Zamknij": "Close",
    "Etykieta": "Label",
    "np. Spotify": "e.g. Spotify",
    "Na ekranie:": "On screen:",
    "Kolor": "Color",
    "Własny…": "Custom…",
    "Kolor klawisza": "Key color",
    "Naciśnięcie": "Tap",
    "Przytrzymanie": "Hold",
    "Podwójne": "Double tap",
    "Przycisk pokrętła": "Knob button",
    "W prawo": "Right",
    "W lewo": "Left",
    "Wciśnięte + w prawo": "Pressed + right",
    "Wciśnięte + w lewo": "Pressed + left",
    "Przycisk": "Button",
    "Szybkie presety": "Quick presets",
    "Obrót bez wciśnięcia": "Rotate (not pressed)",
    "Obrót z wciśniętym przyciskiem": "Rotate while pressed",
    "proces, np. spotify.exe": "process, e.g. spotify.exe",
    "Zastosuj": "Apply",
    "Głośność systemu": "System volume",
    "Głośność programu…": "App volume…",
    "Przewijanie pionowe": "Vertical scroll",
    "Przewijanie poziome": "Horizontal scroll",
    "Utwory (następny/poprzedni)": "Tracks (next/previous)",
    "Zmiana profilu": "Switch profile",
    "Nazwa": "Name",
    "Profil domyślny (start aplikacji)": "Default profile (on app start)",
    "Automatyczne przełączanie": "Automatic switching",
    "Profil włącza się, gdy aktywne jest okno jednego z tych procesów.": "This profile turns on when a window of one of these processes is active.",
    "np. obs64.exe": "e.g. obs64.exe",
    "Odśwież listę uruchomionych procesów": "Refresh running processes",
    # edytor akcji
    "(brak akcji)": "(no action)",
    "nieznany": "unknown",
    "Typ akcji": "Action type",
    "Testuj": "Test",
    "Wykonaj akcję teraz": "Run the action now",
    "Nagraj skrót": "Record shortcut",
    "Anuluj": "Cancel",
    "np. ctrl+shift+c, win+e, f13": "e.g. ctrl+shift+c, win+e, f13",
    "Naciśnij kombinację klawiszy…": "Press a key combination…",
    "Plik…": "File…",
    "Folder…": "Folder…",
    "Programy (*.exe *.bat *.cmd *.lnk);;Wszystkie pliki (*)": "Programs (*.exe *.bat *.cmd *.lnk);;All files (*)",
    "Wszystkie pliki (*)": "All files (*)",
    "Wybierz plik": "Choose file",
    "Wybierz folder": "Choose folder",
    "Edytuj": "Edit",
    "W górę": "Move up",
    "W dół": "Move down",
    "Krok makra": "Macro step",
    "Opóźnienie po kroku:": "Delay after step:",
    # typy akcji (core/actions)
    "Uruchom program": "Launch program",
    "Uruchamia program lub przełącza na jego okno": "Launches a program or switches to its window",
    "Otwórz plik/folder": "Open file/folder",
    "Otwórz adres WWW": "Open web address",
    "Skrót klawiszowy": "Keyboard shortcut",
    "Kombinacja klawiszy, np. Ctrl+Shift+C, Win+E, F13": "Key combination, e.g. Ctrl+Shift+C, Win+E, F13",
    "Wpisz tekst": "Type text",
    "Wpisuje tekst (Unicode, także polskie znaki)": "Types text (Unicode, including accented characters)",
    "Multimedia": "Media",
    "Odtwarzanie i głośność systemu": "Playback and system volume",
    "Głośność programu": "App volume",
    "Głośność wybranego procesu (mikser Windows)": "Volume of a chosen process (Windows mixer)",
    "Przewijanie": "Scroll",
    "Polecenie": "Command",
    "Polecenie cmd lub PowerShell": "cmd or PowerShell command",
    "Makro": "Macro",
    "Lista kroków wykonywanych po kolei": "A list of steps run one after another",
    "Zmień profil": "Switch profile",
    "Warstwa (profil na czas trzymania)": "Layer (profile while held)",
    "Profil aktywny tylko podczas trzymania klawisza": "Profile active only while the key is held",
    "System": "System",
    "Nieznana akcja": "Unknown action",
    # pola akcji
    "Program": "Program",
    "Argumenty": "Arguments",
    "Katalog roboczy": "Working directory",
    "Jeśli już działa, przełącz na jego okno": "If already running, switch to its window",
    "Kolejne naciśnięcia przełączają między oknami programu": "Repeated presses cycle through the program's windows",
    "Plik lub folder": "File or folder",
    "Adres": "Address",
    "Przeglądarka (puste = domyślna)": "Browser (empty = default)",
    "Skrót": "Shortcut",
    "Tekst": "Text",
    "Krok głośności (%)": "Volume step (%)",
    "Proces (np. spotify.exe)": "Process (e.g. spotify.exe)",
    "Działanie": "Action",
    "Głośniej": "Volume up",
    "Ciszej": "Volume down",
    "Wycisz/włącz": "Mute/unmute",
    "Krok (%)": "Step (%)",
    "Kierunek": "Direction",
    "Linii na krok": "Lines per step",
    "Powłoka": "Shell",
    "Ukryte okno": "Hidden window",
    "Limit czasu (s)": "Timeout (s)",
    "Kroki": "Steps",
    "Opóźnienie po kroku (ms)": "Delay after step (ms)",
    "Przełącz na profil": "Switch to profile",
    "Następny": "Next",
    "Poprzedni": "Previous",
    "Zablokuj komputer": "Lock computer",
    "Wyłącz ekran": "Turn off display",
    "Odtwórz/Pauza": "Play/Pause",
    "Następny utwór": "Next track",
    "Poprzedni utwór": "Previous track",
    "Stop": "Stop",
    "Wycisz": "Mute",
    "Następny profil": "Next profile",
    "Poprzedni profil": "Previous profile",
    "Warstwa": "Layer",
    "kroków": "steps",
    # dziennik
    "Ostatnie zdarzenia i błędy.": "Recent events and errors.",
    "Pokaż": "Show",
    "Wszystko": "All",
    "Ostrzeżenia i błędy": "Warnings and errors",
    "Tylko błędy": "Errors only",
    "Wyczyść": "Clear",
    # ustawienia
    "Ustawienia – Tap32": "Settings – Tap32",
    "Urządzenie, gesty, pokrętło, tryb awaryjny i aplikacja.": "Device, gestures, knob, fallback mode and application.",
    "Urządzenie": "Device",
    "Gesty": "Gestures",
    "Tryb awaryjny": "Fallback mode",
    "Aplikacja": "Application",
    "Zapisz": "Save",
    "Port": "Port",
    "Port szeregowy Tap32": "Tap32 serial port",
    "Automatycznie (wykryj Tap32)": "Automatic (detect Tap32)",
    "Jasność ekranu": "Display brightness",
    "Wygaszacz po": "Screen saver after",
    "0 = wyłączony": "0 = off",
    "wyłączony": "off",
    "Tryb ekranu": "Display mode",
    "Obróć ekran o 180°": "Rotate display 180°",
    "Debounce klawiszy": "Key debounce",
    "Akcje urządzenia": "Device actions",
    "Próg przytrzymania": "Hold threshold",
    "Okno podwójnego naciśnięcia": "Double-tap window",
    "Wykonuj „przytrzymanie” od razu po przekroczeniu progu": "Run “hold” as soon as the threshold is passed",
    "Jeśli klawisz nie ma akcji „podwójne”, zwykłe naciśnięcie wykonuje się od razu po puszczeniu. W przeciwnym razie czeka na upływ okna.": "If a key has no “double tap” action, a tap runs immediately on release. Otherwise it waits for the window to pass.",
    "Odwróć kierunek obrotu": "Reverse rotation direction",
    "Impulsy na ząbek": "Pulses per detent",
    "Przyspieszenie przy szybkim kręceniu": "Accelerate when spinning fast",
    "Szybki obrót, gdy odstęp ≤": "Fast spin when interval ≤",
    "Mnożnik kroków": "Step multiplier",
    "Gdy aplikacja nie działa (brak sygnału przez 3 s), Tap32 sam wysyła skróty klawiaturowe/multimedialne przez USB HID. Domyślnie są wyliczane z aktywnego profilu (akcje typu skrót i multimedia), a poniższe wpisy je nadpisują.": "When the app is not running (no signal for 3 s), Tap32 sends keyboard/media shortcuts itself over USB HID. By default they are derived from the active profile (shortcut and media actions); the entries below override them.",
    "Wyliczaj skróty z aktywnego profilu": "Derive shortcuts from the active profile",
    "Element": "Item",
    "Skrót (np. ctrl+c)": "Shortcut (e.g. ctrl+c)",
    "(z profilu)": "(from profile)",
    "Pokrętło w prawo": "Knob right",
    "Pokrętło w lewo": "Knob left",
    "tylko jeden klawisz poza modyfikatorami": "only one key besides modifiers",
    "Język interfejsu aplikacji": "Application interface language",
    "Motyw": "Theme",
    "Według systemu": "Follow system",
    "Jasny": "Light",
    "Ciemny": "Dark",
    "Uruchamiaj z systemem Windows": "Start with Windows",
    "Startuj zminimalizowana do zasobnika": "Start minimized to the tray",
    "Pokazuj etykietę na ekranie po wykonaniu akcji": "Show the label on the display after an action runs",
    "Automatycznie przełączaj profile według aktywnego okna": "Switch profiles automatically by active window",
    # zasobnik
    "Otwórz Tap32": "Open Tap32",
    "Wstrzymaj akcje": "Pause actions",
    "Tap32 – połączono": "Tap32 – connected",
    "Tap32 – rozłączono": "Tap32 – disconnected",
}


def set_language(language: str) -> None:
    global _language
    _language = "en" if language == "en" else "pl"


def language() -> str:
    return _language


def tr(text: str) -> str:
    if _language == "pl" or not text:
        return text
    return EN.get(text, text)


def action_summary(action: ActionBase | None) -> str:
    """Krótki opis akcji na kafelku/w edytorze, w bieżącym języku."""
    if action is None:
        return ""
    kind = action.type
    data = action.model_dump()
    if kind in ("launch", "open"):
        path = str(data.get("path") or "").replace("/", "\\")
        return path.rsplit("\\", 1)[-1] or tr(action.label)
    if kind == "url":
        url = str(data.get("url") or "")
        for prefix in ("https://", "http://"):
            url = url.removeprefix(prefix)
        return url.removeprefix("www.").rstrip("/") or tr(action.label)
    if kind == "hotkey":
        keys = str(data.get("keys") or "")
        try:
            return format_hotkey(parse_hotkey(keys)) if keys else tr("Skrót")
        except ValueError:
            return keys
    if kind == "type_text":
        short = str(data.get("text") or "").replace("\n", " ")[:20]
        return f"„{short}”"
    if kind == "media":
        from ..core.actions.builtin import MEDIA_LABELS

        return tr(str(MEDIA_LABELS.get(data.get("key"), data.get("key"))))
    if kind == "app_volume":
        modes = {"up": "Głośniej", "down": "Ciszej", "mute": "Wycisz/włącz"}
        return f"{data.get('process') or '?'} · {tr(modes.get(data.get('mode'), ''))}"
    if kind == "scroll":
        dirs = {"up": "W górę", "down": "W dół", "left": "W lewo", "right": "W prawo"}
        return f"{tr('Przewijanie')} · {tr(dirs.get(data.get('direction'), ''))}"
    if kind == "macro":
        return f"{tr('Makro')} ({len(data.get('steps') or [])} {tr('kroków')})"
    if kind == "profile":
        mode = data.get("mode")
        if mode == "next":
            return tr("Następny profil")
        if mode == "prev":
            return tr("Poprzedni profil")
        return f"{tr('Profil')}: {data.get('profile') or '—'}"
    if kind == "layer":
        return f"{tr('Warstwa')}: {data.get('profile') or '—'}"
    if kind == "system":
        cmds = {"lock": "Zablokuj komputer", "screen_off": "Wyłącz ekran"}
        return tr(cmds.get(data.get("command"), tr("System")))
    if kind == "shell":
        return f"{data.get('shell')}: {str(data.get('command') or '')[:24]}"
    return tr(action.label) if action.label else action.type
