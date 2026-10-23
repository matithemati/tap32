# Tap32

Tap32 to przewodowy macropad z 9 klawiszami MX (matryca 3×3), pokrętłem EC11 z przyciskiem i
ekranem OLED 0.91" (128×32), oparty na **Adafruit KB2040** (RP2040) albo **Seeed XIAO ESP32-S3**,
oraz aplikacja na Windows, w której ustawiasz, co robi każdy klawisz i pokrętło.

Firmware jest „cienki”: skanuje klawisze i pokrętło, rysuje ekran i przechowuje kilka ustawień.
Całą logikę (gesty, akcje, profile) wykonuje aplikacja na PC. Komunikują się przez USB CDC
protokołem JSON Lines ([docs/PROTOCOL.md](docs/PROTOCOL.md)). Gdy aplikacja nie działa,
urządzenie samo wysyła zapisane skróty przez USB HID (tryb awaryjny).

```
firmware/   PlatformIO: środowiska kb2040, xiao_esp32s3, native (testy)
app/        aplikacja Python 3.12+ (PySide6): rdzeń, GUI, symulator, testy
case/       parametryczna obudowa OpenSCAD
docs/       PROTOCOL.md, WIRING.md
```

## Funkcje

- **Gesty**: naciśnięcie, przytrzymanie (próg 500 ms), podwójne naciśnięcie (okno 300 ms);
  pokrętło: obrót w prawo/lewo i obrót z wciśniętym przyciskiem, opcjonalne przyspieszenie.
- **Akcje**: uruchom program (albo przełącz na jego okno), otwórz plik/folder, adres WWW,
  skrót klawiszowy (także Win, F13–F24), wpisz tekst (Unicode), multimedia, głośność
  systemu i pojedynczego programu, przewijanie, polecenie cmd/PowerShell, makro, zmiana
  profilu, warstwa (profil na czas trzymania klawisza), blokada komputera, wyłączenie ekranu.
- **Profile** z automatycznym przełączaniem według aktywnego okna (np. `obs64.exe` → „Stream”),
  import/eksport do JSON.
- **Ekran**: siatka etykiet 3×3 albo duża nazwa profilu, pasek głośności, etykieta po akcji,
  wygaszacz, znacznik online/offline, tryb testu sprzętu.
- **Tryb awaryjny HID**: po 3 s bez sygnału z aplikacji pokrętło zmienia głośność, przycisk
  wycisza, klawisze wysyłają skróty wyliczone z profilu (akcje „skrót” i „multimedia”).

## Wybór płytki

| | Adafruit KB2040 | Seeed XIAO ESP32-S3 |
|---|---|---|
| Mikrokontroler | RP2040 | ESP32-S3 |
| Rozmiar | ok. 33 × 18 mm | 21 × 17,8 mm |
| Wolne GPIO po podłączeniu | kilka (np. STEMMA QT) | 0 (wszystkie 11 zajęte) |
| Dioda statusu | NeoPixel (kolory) | jedna LED (świeci/miga) |
| Wgrywanie | dysk RPI-RP2 (UF2) | port USB (esptool) |
| Pamięć ustawień | LittleFS | NVS (Preferences) |

Obie działają tak samo z aplikacją – rozpoznaje je po nazwie produktu USB „Tap32”.
KB2040 jest prostszy w uruchomieniu (UF2, NeoPixel), XIAO – mniejszy.

## Części

- 1× Adafruit KB2040 **albo** Seeed XIAO ESP32-S3
- 9× przełącznik MX (+ nasadki), 9× dioda 1N4148
- 1× enkoder EC11 z przyciskiem (tuleja M7) + gałka
- 1× OLED 0.91" SSD1306 128×32 I²C (adres 0x3C)
- przewody, obudowa (wydruk 3D z `case/`), 4 wkręty M2 (lub M3)

## Montaż

Pełny opis i tabele pinów: **[docs/WIRING.md](docs/WIRING.md)**. Najważniejsze:

1. Matryca **COL2ROW**: przy każdym przełączniku dioda 1N4148, **pasek (katoda) w stronę wiersza**.
   Wiersze R1–R3 i kolumny C1–C3 podłącz według tabeli dla wybranej płytki.
2. Enkoder: A, B, SW na GPIO; wspólny pin C i druga nóżka przycisku do GND.
3. OLED: VCC → **3,3 V**, GND, SDA, SCL.
4. Uruchom tryb testu sprzętu (przytrzymaj **K1 + K3** zaraz po podłączeniu, przez 3 s) i sprawdź
   każdy klawisz, przycisk i kierunek pokrętła.

## Firmware

Wymagania: [PlatformIO](https://platformio.org/) (VS Code + rozszerzenie albo `pip install platformio`).

```bash
cd firmware
pio run -e kb2040
```

```bash
pio run -e xiao_esp32s3
```

Wersje (sprawdzone 2026-10): U8g2 2.36.18, ArduinoJson 7.4.3, Adafruit NeoPixel 1.15.5.

- **KB2040**: platforma `maxgerhardt/platform-raspberrypi` (rdzeń arduino-pico Earle Philhowera),
  płytka `adafruit_kb2040`, stos Adafruit TinyUSB (`-DUSE_TINYUSB`): CDC + HID (klawiatura i
  consumer control). Nazwa USB ustawiona przez `board_build.arduino.earlephilhower.usb_product`.
- **XIAO ESP32-S3**: oficjalna platforma `espressif32` w PlatformIO nadal dostarcza Arduino-ESP32 2.x,
  dlatego używamy **pioarduino** `53.03.13` (Arduino-ESP32 **3.1.3**), płytka `seeed_xiao_esp32s3`.
  Definicja płytki domyślnie ustawia `ARDUINO_USB_MODE=1` (sprzętowy CDC/JTAG – bez HID), więc
  `platformio.ini` nadpisuje `board_build.extra_flags` na `ARDUINO_USB_MODE=0` +
  `ARDUINO_USB_CDC_ON_BOOT=1` (TinyUSB: CDC + HID). Nazwa USB przez `-DUSB_PRODUCT="Tap32"`.
  Uwaga: wariant XIAO ma **własny VID Seeed 0x2886** (nie Espressif 0x303A) – aplikacja szuka
  wszystkich trzech VID (0x303A, 0x239A, 0x2886) i zawsze potwierdza urządzenie wiadomością `hello`.
- `lib_ldf_mode = chain+` – wykrywanie bibliotek respektuje `#if`, dzięki czemu HAL jednej płytki
  nie wciąga bibliotek drugiej.

### Wgrywanie – KB2040

1. Przytrzymaj **BOOT**, naciśnij i puść **RESET**, puść BOOT → pojawi się dysk **RPI-RP2**.
2. Skopiuj `firmware/.pio/build/kb2040/firmware.uf2` na ten dysk (płytka sama się zrestartuje).

Albo bezpośrednio: `pio run -e kb2040 -t upload` (działa też z działającym firmware Tap32 – reset
przez „1200 bps touch”). Z aplikacji: menu **Urządzenie → Tryb wgrywania firmware**.

### Wgrywanie – XIAO ESP32-S3

1. Trzymając przycisk **BOOT** (B), podłącz kabel USB-C (albo: trzymaj BOOT i naciśnij RESET).
2. `pio run -e xiao_esp32s3 -t upload`
3. Po wgraniu naciśnij **RESET** (w trybie pobierania płytka nie uruchamia się sama).

Przy kolejnych aktualizacjach można użyć menu aplikacji **Urządzenie → Tryb wgrywania firmware**.

### Testy firmware (na PC)

Parser protokołu, dekoder enkodera (sekwencje A/B z drganiami), debounce, kody HID i zapis
konfiguracji mają testy jednostkowe w środowisku `native`. Potrzebny jest kompilator gcc/g++
w PATH (Windows: MSYS2/MinGW-w64; najprościej `pio pkg install -g -t platformio/toolchain-gccmingw32`
i dodanie `%USERPROFILE%\.platformio\packages\toolchain-gccmingw32\bin` do PATH).

```bash
pio test -e native
```

## Aplikacja

Wymagania: Windows 10/11, Python **3.12+** (sprawdzone na 3.14).

```bash
cd app
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m tap32
```

Opcje:

| Opcja | Działanie |
|---|---|
| `--simulate` | zamiast urządzenia uruchamia **symulator** (okno z 9 klawiszami, pokrętłem – kółko myszy – i podglądem OLED) |
| `--board xiao_esp32s3` | płytka zgłaszana przez symulator |
| `--minimized` | start w zasobniku |
| `--config PLIK` | inny plik konfiguracji |
| `--verbose` | dziennik na konsoli |

Konfiguracja: `%APPDATA%\Tap32\config.json` (zapis atomowy, poprzednia wersja w `config.json.bak`,
dziennik w `tap32.log`). Uszkodzony plik jest odkładany jako `config.broken.json`, a aplikacja
wczytuje kopię zapasową.

Obsługa:

- Lista profili po lewej (dwuklik = aktywuj). Kliknij klawisz albo pokrętło na podglądzie, aby
  edytować; przyciski **Testuj** wykonują akcję od razu. Fizyczne naciśnięcia podświetlają elementy.
- **Plik → Ustawienia**: port (auto/ręczny), jasność, wygaszacz, tryb ekranu, obrót, progi gestów,
  pokrętło (odwrócenie, impulsy na ząbek, przyspieszenie), debounce, skróty trybu awaryjnego,
  autostart z Windows, start zminimalizowany, motyw.
- Zamknięcie okna chowa aplikację do zasobnika (kolor ikony = stan połączenia). Z zasobnika:
  zmiana profilu, **Wstrzymaj akcje**, wyjście. Uruchamia się tylko jedna instancja.

### Testy i jakość

```bash
cd app
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check tap32 tests
.venv\Scripts\python -m ruff format --check tap32 tests
.venv\Scripts\python -m mypy tap32
```

Testy nie wymagają urządzenia (atrapy portu szeregowego, platformy i symulator). Testy GUI
działają w trybie `offscreen` (pytest-qt).

### Budowanie Tap32.exe

```powershell
cd app
.\build_exe.ps1
```

Skrypt instaluje zależności, generuje ikonę (`scripts/make_icon.py`) i uruchamia PyInstaller
(`tap32.spec`, jeden plik, bez konsoli). Wynik: `app\dist\Tap32.exe`.

### Architektura aplikacji

```
tap32/core/protocol.py    kodowanie/dekodowanie JSON Lines, walidacja, transliteracja (OLED = ASCII)
tap32/core/transport.py   interfejs + port szeregowy (wątek, wykrywanie, ponowne łączenie)
tap32/core/simulator.py   symulator urządzenia (ta sama logika co firmware) + transport w procesie
tap32/core/gestures.py    tap / hold / double_tap / obroty (czysta logika, czas z zewnątrz)
tap32/core/actions/       rejestr typów akcji, wbudowane akcje, wykonawca (pula wątków)
tap32/core/config.py      modele pydantic, migracje schema_version, zapis atomowy, import/eksport
tap32/core/profiles.py    aktywny profil, warstwy, automatyczne przełączanie
tap32/core/engine.py      kontroler: zdarzenia → gesty → akcje; profil → display + set_fallback
tap32/platform/           kod zależny od systemu (windows.py; base.py = interfejs dla Linux/macOS)
tap32/gui/                PySide6: okno główne, edytory, ustawienia, zasobnik, symulator
```

Nowy typ akcji: klasa dziedzicząca po `ActionBase` z polem `type: Literal["nazwa"]`, metodą
`run(ctx)` i dekoratorem `@register_action("nazwa", "Etykieta")`. Formularz w GUI tworzy się
automatycznie z pól modelu.

## Obudowa (OpenSCAD)

`case/tap32_case.scad` – parametry na początku pliku (płytka, otwór MX 14,0 mm, rozstaw 19,05 mm,
płyta 1,5 mm, okno OLED, otwór 7,2 mm na EC11, śruby M2/M3, pochylenie `tilt_deg`).

```bash
openscad -D part=\"top\" -D board=\"kb2040\" -o tap32_top.stl case/tap32_case.scad
```

```bash
openscad -D part=\"bottom\" -D board=\"kb2040\" -D tilt_deg=6 -o tap32_bottom.stl case/tap32_case.scad
```

Górę drukuj płytą do stołu (plik jest już obrócony), dół – bez podpór. Moduł OLED wkleja się
w ramkę prowadzącą od spodu, enkoder przykręca nakrętką M7, płytka wsuwa się w uchwyt przy tylnej
ściance (USB-C w wycięciu).

## Rozwiązywanie problemów

| Objaw | Co sprawdzić |
|---|---|
| Aplikacja „szuka Tap32…” | Kabel z transmisją danych (nie tylko ładowanie). Zamknij monitor portu PlatformIO/Arduino IDE (port może być zajęty). W Ustawieniach wybierz port ręcznie. Dziennik pokazuje próby. |
| XIAO nie pojawia się jako klawiatura / brak portu | Firmware musi być zbudowany z `ARDUINO_USB_MODE=0` (środowisko `xiao_esp32s3`). Po wgraniu naciśnij RESET. |
| Nie da się wgrać na XIAO | Wejdź w tryb pobierania: BOOT + podłączenie kabla. |
| KB2040 nie widać jako dysku | BOOT trzymany podczas RESET; inny kabel/port. |
| Pusty ekran | Spójrz na pasek stanu aplikacji: **OLED: 0x3C/0x3D** = ekran odpowiada (adres wybierany automatycznie), **OLED: brak** = nic nie odpowiada na I²C – sprawdź zasilanie 3,3 V, GND, zamienione SDA/SCL i lutowanie. Lista znalezionych urządzeń jest w zakładce Dziennik. |
| Pokrętło liczy podwójnie / co drugi ząbek | Ustawienia → Pokrętło → **Impulsy na ząbek** (EC11 zwykle 4, niektóre 2). |
| Pokrętło kręci odwrotnie | Ustawienia → Pokrętło → **Odwróć kierunek**. |
| Kilka klawiszy reaguje naraz | Odwrócona dioda albo brak diody; sprawdź w trybie testu sprzętu. |
| Klawisz „drga” | Zwiększ debounce (Ustawienia → Urządzenie). |
| Przełączanie na okno programu nie działa | Windows czasem blokuje przejęcie fokusu; program i tak jest uruchamiany, gdy nie ma okna. |
| Głośność programu „nie gra” | Program musi mieć aktywną sesję audio (widoczną w mikserze głośności). |
| SmartScreen / antywirus ostrzega o Tap32.exe | Plik nie jest podpisany; pynput (symulacja klawiatury) bywa oznaczany heurystycznie. Można uruchamiać z Pythona. |
| Akcje wykonują się podwójnie | Nie powinno: gdy aplikacja jest połączona, HID urządzenia jest wyłączony. Sprawdź, czy nie działają dwie kopie aplikacji (np. exe i python). |

## Licencja

MIT.
