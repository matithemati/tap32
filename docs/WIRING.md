# Okablowanie Tap32

## Matryca 3×3 (COL2ROW)

Każdy przełącznik MX ma szeregowo diodę **1N4148**. Układ **COL2ROW**: prąd płynie od
kolumny przez przełącznik i diodę do wiersza – **katoda diody (pasek) w stronę wiersza**.

```
           COL1 (in, pull-up)   COL2               COL3
             │                   │                  │
ROW1 ──┬─────┼──────────┬────────┼─────────┬────────┼──
 (out) │     │          │        │         │        │
       ▼ D1  └─[K1]─┐   ▼ D2     └─[K2]─┐  ▼ D3     └─[K3]─┐
       └────────────┘   └───────────────┘  └───────────────┘
   (analogicznie ROW2: K4 K5 K6, ROW3: K7 K8 K9)
```

Schemat pojedynczego klawisza:

```
COLn ───[ przełącznik ]───|>|─── ROWm
                          A  K   (katoda/pasek → wiersz)
```

Skanowanie: aktywny wiersz = wyjście **LOW**, pozostałe wiersze = wejście (wysoka impedancja).
Kolumny = wejścia z **INPUT_PULLUP**. Wciśnięty klawisz w aktywnym wierszu ściąga kolumnę do LOW.
Dzięki diodom możliwe jest pełne NKRO (dowolna kombinacja klawiszy bez „duchów”).

Numeracja: `Kn`, n = (wiersz − 1)·3 + kolumna.

| | COL1 | COL2 | COL3 |
|---|---|---|---|
| **ROW1** | K1 | K2 | K3 |
| **ROW2** | K4 | K5 | K6 |
| **ROW3** | K7 | K8 | K9 |

Przycisk enkodera = **klawisz 10** (poza matrycą).

## Enkoder EC11 z przyciskiem

```
EC11 (widok od strony nóżek)
  A ─── GPIO enc A (INPUT_PULLUP)
  C ─── GND
  B ─── GPIO enc B (INPUT_PULLUP)
  SW1 ── GPIO enc SW (INPUT_PULLUP)
  SW2 ── GND
```
Opcjonalnie: kondensatory 10 nF z A i B do GND poprawiają odporność na drgania
(firmware i tak filtruje je tablicą stanów kodu Graya).

## OLED 0.91" SSD1306 128×32 (I²C)

| OLED | Połączenie |
|---|---|
| GND | GND |
| VCC | **3,3 V** |
| SCL | SCL płytki |
| SDA | SDA płytki |

Adres domyślny **0x3C** (zmiana: `TAP32_OLED_ADDR` w `firmware/src/config.h` lub ustawienie `oled_addr`).
Moduły OLED mają zwykle własne rezystory podciągające 4,7–10 kΩ.

## Mapa pinów

| Sygnał | KB2040 (GPIO) | XIAO ESP32-S3 (pin / GPIO) |
|---|---|---|
| Wiersz 1 | 9 (D9) | D8 / 7 |
| Wiersz 2 | 8 (D8) | D9 / 8 |
| Wiersz 3 | 7 (D7) | D10 / 9 |
| Kolumna 1 | 6 (D6) | D2 / 3 (strapping) |
| Kolumna 2 | 5 (D5) | D6 / 43 (UART0 TX) |
| Kolumna 3 | 4 (D4) | D7 / 44 (UART0 RX) |
| Enkoder A | 19 (MOSI) | D0 / 1 |
| Enkoder B | 20 (MISO) | D1 / 2 |
| Enkoder SW | 18 (SCK) | D3 / 4 |
| OLED SDA | 0 (D0, I²C0) | D4 / 5 |
| OLED SCL | 1 (D1, I²C0) | D5 / 6 |
| Dioda statusu | NeoPixel GPIO17 (wbudowany) | LED użytkownika GPIO21 (wbudowana, aktywna stanem niskim) |

Plik źródłowy prawdy: `firmware/src/boards/board_kb2040.h` i `board_xiao_esp32s3.h`.

### Uwagi – KB2040

- I²C0 na GPIO0/1 (`Wire.setSDA(0); Wire.setSCL(1);`). UART0 na tych pinach **nie jest** inicjalizowany.
- NeoPixel na GPIO17 jest wbudowany na płytce. Jasność ograniczona programowo.
- Złącze STEMMA QT (GPIO12/13) nie jest używane.

### Uwagi – XIAO ESP32-S3

- Zajęte są wszystkie 11 pinów D0–D10.
- **GPIO3 (D2)** to pin strapping (wybór źródła JTAG) – wejście z pull-upem jest bezpieczne.
- **GPIO43/44 (D6/D7)** to domyślnie UART0. Firmware nie inicjalizuje `Serial0`; po starcie są
  zwykłymi wejściami kolumn. Bootloader ROM wypisuje komunikaty na GPIO43 przy starcie – diody
  matrycy i wysoka impedancja wierszy sprawiają, że jest to nieszkodliwe.
- Wbudowana pomarańczowa dioda LED użytkownika na GPIO21 świeci przy stanie **niskim**.
- Komunikacja z PC i HID idą przez natywne USB (TinyUSB, `ARDUINO_USB_MODE=0`).

## Zasilanie

Całość zasilana z USB-C płytki. OLED wyłącznie z 3,3 V. Nie podłączaj 5 V do żadnego GPIO.
