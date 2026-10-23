# Protokół Tap32 (wersja 1)

Urządzenie Tap32 i aplikacja na PC komunikują się przez **USB CDC** (wirtualny port
szeregowy, prędkość bez znaczenia – transmisja jest natywna USB). Format: **JSON Lines** –
każda wiadomość to jeden obiekt JSON zakończony znakiem `\n` (`\r` przed `\n` jest
ignorowany). Kodowanie: UTF-8.

Wspólne zasady:

- Każda wiadomość ma pole `type` (string).
- Nieznane pola są **ignorowane** (kompatybilność wsteczna). Nieznane typy wiadomości
  również są ignorowane (bez odpowiedzi, nawet jeśli mają `id`).
- Maksymalna długość linii wysyłanej do urządzenia: **1024 bajty** (łącznie z `\n`).
  Dłuższa linia jest odrzucana w całości, urządzenie odpowiada `error` bez `id`.
- Niepoprawny JSON (lub brak `type`) → `{"type":"error","msg":"..."}` (bez `id`);
  urządzenie nie zawiesza się i czeka na kolejną linię.
- Czasy `t` to milisekundy od startu urządzenia (`millis()`, uint32, przepełnia się po ~49 dniach).

## Urządzenie → PC

### `hello`
```json
{"type":"hello","device":"tap32","fw":"1.0.0","board":"kb2040","keys":10,"encoder":true,"hid":true,"online":false}
```
- `board`: `"kb2040"` lub `"xiao_esp32s3"`.
- `keys`: liczba klawiszy (9 w matrycy + przycisk enkodera = 10).
- `hid`: urządzenie ma interfejs HID (tryb awaryjny).
- `online` (informacyjnie): czy urządzenie uważa aplikację za połączoną.

Wysyłane: po starcie, w odpowiedzi na `hello` od PC i na `get_info`.

### `key`
```json
{"type":"key","key":3,"action":"down","t":123456}
```
- `key`: 1–9 = klawisze matrycy (K1…K9), **10 = przycisk enkodera**.
- `action`: `"down"` | `"up"` (po debounce).

### `enc`
```json
{"type":"enc","steps":-2,"t":123470}
```
- `steps`: liczba ząbków (detentów) od poprzedniej wiadomości `enc`; plus = obrót w prawo (CW),
  minus = w lewo (CCW). Uwzględnia ustawienie `enc_reverse`.
- Urządzenie agreguje kroki i wysyła `enc` najwyżej co ~10 ms.

### `ack` / `error`
```json
{"type":"ack","id":7}
{"type":"error","id":7,"msg":"value out of range"}
{"type":"error","msg":"invalid json"}
```
Odpowiedź na wiadomość z polem `id` (liczba całkowita). `error` bez `id` – błąd parsowania.

### `log`
```json
{"type":"log","level":"info","msg":"settings saved"}
```
Tylko w trybie debug (`{"type":"debug","enable":true}`). `level`: `debug` | `info` | `warn` | `error`.

### `test`
```json
{"type":"test","active":true}
```
Informuje o wejściu/wyjściu z trybu testu sprzętu.

## PC → urządzenie

Pole `id` jest opcjonalne w każdej wiadomości. Jeśli występuje, urządzenie odpowiada
`ack` (sukces) albo `error` (błąd walidacji).

### `hello`
```json
{"type":"hello","app":"1.0.0"}
```
Urządzenie odpowiada `hello` i przechodzi w stan **online**.

### `ping`
```json
{"type":"ping"}
```
Wysyłany przez aplikację **co 1 s**. Każda poprawna wiadomość od PC odświeża licznik
heartbeat, ale aplikacja musi wysyłać `ping`, gdy nie ma nic innego do wysłania.
**Brak wiadomości przez 3 s → urządzenie przechodzi w tryb offline** (patrz niżej).

### `get_info`
```json
{"type":"get_info"}
```
Urządzenie odpowiada `hello`.

### `display`
Ustawia główny tryb ekranu. Tryby `profile` i `grid` są trwałe (zapamiętywane w pamięci
urządzenia). Tryby z polem `ms` (`text`, `bar`) są chwilowe – po `ms` ekran wraca do
poprzedniego trybu trwałego.

```json
{"type":"display","mode":"profile","name":"Stream"}
{"type":"display","mode":"grid","title":"Domyślny","labels":["Calc","Notes","Pliki","WWW","Kopiuj","Wklej","Play","<","Profil"]}
{"type":"display","mode":"text","line1":"Hello","line2":"world","ms":2000}
{"type":"display","mode":"bar","title":"Głośność","value":42,"ms":1500}
```
| Pole | Tryb | Limit |
|---|---|---|
| `name` | profile | 21 znaków |
| `title` | grid, bar | 21 znaków |
| `labels` | grid | 9 napisów, każdy do **7 znaków**; brakujące = puste |
| `line1`, `line2` | text | po 21 znaków |
| `value` | bar | 0–100 (przycinane) |
| `ms` | text, bar | 0 = bez limitu (tryb staje się trwały, ale nie jest zapisywany) |

Dłuższe napisy są obcinane. Czcionki urządzenia obsługują ASCII; znaki spoza ASCII
aplikacja **transliteruje** (ą→a, ł→l, …) przed wysłaniem.

### `flash`
```json
{"type":"flash","key":3,"text":"Spotify","ms":1200}
```
Chwilowy duży napis (np. po wykonaniu akcji). `key` (opcjonalny) wyświetlany jest małym
znacznikiem `K3`. `ms` domyślnie 1000, maks. 10000.

### `settings`
Częściowa aktualizacja ustawień (podaj tylko zmieniane pola). Ustawienia są zapisywane
w pamięci nieulotnej.

```json
{"type":"settings","id":3,"brightness":128,"screensaver_s":300,"flip":false,"enc_reverse":false,"enc_pulses":4,"debounce_ms":8}
```
| Pole | Typ | Zakres | Domyślnie |
|---|---|---|---|
| `brightness` | int | 0–255 (kontrast OLED) | 128 |
| `screensaver_s` | int | 0–65535, 0 = wyłączony | 300 |
| `flip` | bool | obrót ekranu o 180° | false |
| `enc_reverse` | bool | odwrócenie kierunku pokrętła | false |
| `enc_pulses` | int | 1–8 impulsów (zmian stanu A/B) na ząbek | 4 |
| `debounce_ms` | int | 1–50 | 8 |
| `oled_addr` | int | adres I²C OLED (0x3C / 0x3D), działa po restarcie | 0x3C |

Wartość poza zakresem lub złego typu → `error`, żadne pole z tej wiadomości nie jest zapisywane.

### `set_fallback`
Skróty HID dla trybu awaryjnego (offline). Można wysłać pojedyncze przypisanie albo listę:

```json
{"type":"set_fallback","key":1,"mods":["ctrl","shift"],"code":"c"}
{"type":"set_fallback","key":10,"media":"mute"}
{"type":"set_fallback","replace":true,"bindings":[
  {"key":"enc_cw","media":"vol_up"},
  {"key":"enc_ccw","media":"vol_down"},
  {"key":10,"media":"mute"},
  {"key":2,"mods":["ctrl"],"code":"v"}
]}
```
- `key`: 1–10 lub `"enc_cw"` / `"enc_ccw"`.
- `mods`: lista z `ctrl`, `shift`, `alt`, `win` (alias `gui`, `meta`), opcjonalnie z prefiksem
  `r` dla prawego (`rctrl`, `rshift`, `ralt`, `rwin`).
- `code`: nazwa klawisza (patrz niżej) albo liczba – surowy kod HID Usage (Keyboard page 0x07).
- `media`: `play_pause`, `next`, `prev`, `stop`, `vol_up`, `vol_down`, `mute`.
- Przypisanie bez `code` i `media` (oraz bez `mods`) usuwa skrót klawisza.
- `replace: true` czyści wszystkie przypisania przed zastosowaniem listy.

Nazwy klawiszy (`code`): `a`–`z`, `0`–`9`, `f1`–`f24`, `enter`, `esc`, `backspace`, `tab`,
`space`, `minus`, `equal`, `lbracket`, `rbracket`, `backslash`, `semicolon`, `quote`,
`grave`, `comma`, `period`, `slash`, `capslock`, `printscreen`, `scrolllock`, `pause`,
`insert`, `home`, `pageup`, `delete`, `end`, `pagedown`, `right`, `left`, `down`, `up`,
`numlock`, `kp_0`–`kp_9`, `kp_plus`, `kp_minus`, `kp_multiply`, `kp_divide`, `kp_enter`,
`kp_period`, `menu`. Pojedyncze znaki `-` `=` `[` `]` `\` `;` `'` `` ` `` `,` `.` `/` też są akceptowane.

Domyślne przypisania (gdy nic nie zapisano): pokrętło CW = `vol_up`, CCW = `vol_down`,
przycisk enkodera = `mute`, klawisze 1–9 bez przypisania.

### `reboot`
```json
{"type":"reboot"}
{"type":"reboot","bootloader":true}
```
`bootloader: true`: ESP32-S3 → tryb pobierania ROM (USB DFU/JTAG-serial), RP2040 → dysk
`RPI-RP2` (UF2). Urządzenie wysyła `ack` (jeśli było `id`) przed restartem.

### `test_mode`
```json
{"type":"test_mode","enable":true}
```
Włącza/wyłącza tryb testu sprzętu (ekran na żywo pokazuje stan klawiszy i licznik enkodera).
Tryb można też włączyć, trzymając **K1 + K3 przez 3 s zaraz po starcie**; wyłączyć – komendą
albo ponownym przytrzymaniem K1 + K3 przez 3 s.

### `debug`
```json
{"type":"debug","enable":true}
```
Włącza wysyłanie wiadomości `log`.

## Tryb online / offline (heartbeat)

| Stan | Warunek | Zachowanie |
|---|---|---|
| offline (start) | brak `hello`/`ping` od startu | ekran „Offline / Czekam na aplikację…”, HID aktywny |
| online | odebrano poprawną wiadomość w ciągu ostatnich 3 s | HID **wyłączony**, ekran wg `display` |
| offline | brak wiadomości przez 3 s | HID wysyła skróty `set_fallback`, ekran „Offline” |

Zdarzenia `key` i `enc` są wysyłane **zawsze**, także offline. Przy przejściu offline → online
urządzenie zwalnia wszystkie wciśnięte klawisze HID (brak „zawieszonych” klawiszy i zdublowanych akcji).

## Przykładowa sesja

```
PC  → {"type":"hello","app":"1.0.0"}
DEV → {"type":"hello","device":"tap32","fw":"1.0.0","board":"kb2040","keys":10,"encoder":true,"hid":true,"online":true}
PC  → {"type":"settings","id":1,"brightness":200}
DEV → {"type":"ack","id":1}
PC  → {"type":"display","mode":"grid","title":"Domyslny","labels":["Calc","Notes","Pliki","WWW","Kopiuj","Wklej","Play","<","Profil"]}
DEV → {"type":"key","key":1,"action":"down","t":5021}
DEV → {"type":"key","key":1,"action":"up","t":5130}
PC  → {"type":"flash","key":1,"text":"Calc","ms":1000}
DEV → {"type":"enc","steps":2,"t":6000}
PC  → {"type":"display","mode":"bar","title":"Glosnosc","value":54,"ms":1500}
PC  → {"type":"ping"}
```
