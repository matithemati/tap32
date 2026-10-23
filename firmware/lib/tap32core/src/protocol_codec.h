// Kodowanie i dekodowanie wiadomości protokołu Tap32 (JSON Lines), patrz docs/PROTOCOL.md.
// Czysta logika – bez Arduino, testowana w środowisku native.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "device_config.h"

namespace tap32 {

constexpr size_t kMaxLineLength = 1024;

enum class CommandType : uint8_t {
  Unknown = 0,
  Hello,
  Ping,
  GetInfo,
  Display,
  Flash,
  Settings,
  SetFallback,
  Reboot,
  TestMode,
  Debug,
};

struct DisplayCommand {
  DisplayMode mode = DisplayMode::None;
  char title[kTitleBuf] = {0};  // grid/bar: tytuł, profile: nazwa
  char labels[kMatrixKeys][kLabelBuf] = {{0}};
  char line1[kTitleBuf] = {0};
  char line2[kTitleBuf] = {0};
  uint8_t value = 0;
  uint32_t ms = 0;
};

struct FlashCommand {
  uint8_t key = 0;  // 0 = brak
  char text[kTitleBuf] = {0};
  uint32_t ms = 1000;
};

// Częściowa aktualizacja ustawień: bit w `mask` oznacza obecność pola.
struct SettingsPatch {
  enum Field : uint16_t {
    kBrightness = 1 << 0,
    kScreensaver = 1 << 1,
    kFlip = 1 << 2,
    kEncReverse = 1 << 3,
    kEncPulses = 1 << 4,
    kDebounce = 1 << 5,
    kOledAddr = 1 << 6,
  };
  uint16_t mask = 0;
  Settings values;

  void applyTo(Settings& s) const;
};

struct FallbackPatch {
  bool replace = false;
  uint8_t count = 0;
  uint8_t slots[kFallbackSlots] = {0};
  FallbackBinding bindings[kFallbackSlots];

  void applyTo(FallbackBinding (&target)[kFallbackSlots]) const;
};

struct Command {
  CommandType type = CommandType::Unknown;
  bool hasId = false;
  int32_t id = 0;
  DisplayCommand display;
  FlashCommand flash;
  SettingsPatch settings;
  FallbackPatch fallback;
  bool flag = false;  // reboot.bootloader / test_mode.enable / debug.enable
};

enum class ParseStatus : uint8_t {
  Ok,          // poprawna komenda
  Ignored,     // nieznany typ – ignorować
  BadJson,     // niepoprawny JSON / brak type – odpowiedź error bez id
  Invalid,     // błąd walidacji – odpowiedź error z id (jeśli jest)
};

struct ParseResult {
  ParseStatus status = ParseStatus::Ok;
  const char* error = nullptr;  // statyczny opis błędu
};

ParseResult parseCommand(const char* line, size_t len, Command& out);

// Budowanie wiadomości wychodzących. Zwracają długość (bez \0, bez \n) lub 0 przy braku miejsca.
size_t buildHello(char* buf, size_t cap, const char* board, const char* fw, bool online);
size_t buildKey(char* buf, size_t cap, uint8_t key, bool down, uint32_t t);
size_t buildEnc(char* buf, size_t cap, int32_t steps, uint32_t t);
size_t buildAck(char* buf, size_t cap, int32_t id);
size_t buildError(char* buf, size_t cap, bool hasId, int32_t id, const char* msg);
size_t buildLog(char* buf, size_t cap, const char* level, const char* msg);
size_t buildTest(char* buf, size_t cap, bool active);

}  // namespace tap32
