// Model danych zapisywanych w pamięci urządzenia (niezależny od płytki) i jego kodek JSON.
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace tap32 {

constexpr int kMatrixKeys = 9;
constexpr int kEncoderKey = 10;  // przycisk enkodera
constexpr int kTotalKeys = 10;

// Limity napisów (w znakach Unicode) i rozmiary buforów (w bajtach UTF-8, z \0).
constexpr size_t kTitleChars = 21;
constexpr size_t kLabelChars = 7;
constexpr size_t kTitleBuf = 48;
constexpr size_t kLabelBuf = 24;

struct Settings {
  uint8_t brightness = 128;
  uint16_t screensaverS = 300;
  bool flip = false;
  bool encReverse = false;
  uint8_t encPulses = 4;
  uint8_t debounceMs = 8;
  uint8_t oledAddr = 0x3C;
};

// Skrót trybu awaryjnego: kombinacja klawiatury (mods + code) albo klawisz multimedialny.
struct FallbackBinding {
  uint8_t mods = 0;
  uint8_t code = 0;
  uint16_t media = 0;
  bool empty() const { return mods == 0 && code == 0 && media == 0; }
};

// Sloty: 0..9 = klawisze 1..10, 10 = obrót CW, 11 = obrót CCW.
constexpr int kSlotEncCw = 10;
constexpr int kSlotEncCcw = 11;
constexpr int kFallbackSlots = 12;

enum class DisplayMode : uint8_t { None = 0, Profile, Grid, Text, Bar };

// Trwały stan ekranu (tylko tryby profile / grid).
struct DisplayState {
  DisplayMode mode = DisplayMode::None;
  char title[kTitleBuf] = {0};  // tytuł siatki albo nazwa profilu
  char labels[kMatrixKeys][kLabelBuf] = {{0}};
};

struct DeviceConfig {
  Settings settings;
  FallbackBinding fallback[kFallbackSlots];
  DisplayState display;

  void setDefaults();
  static void defaultFallback(FallbackBinding (&slots)[kFallbackSlots]);
};

// Zwraca liczbę zapisanych bajtów (0 przy braku miejsca).
size_t encodeConfig(const DeviceConfig& cfg, char* buf, size_t cap);
// Zwraca false, jeśli dane są uszkodzone (wtedy cfg ma wartości domyślne).
bool decodeConfig(const char* json, size_t len, DeviceConfig& cfg);

// Kopiuje UTF-8 obcinając do maxChars znaków i rozmiaru bufora, bez łamania sekwencji.
void copyUtf8(char* dst, size_t dstSize, const char* src, size_t maxChars);

}  // namespace tap32
