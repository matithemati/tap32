// Mapowanie nazw klawiszy/modyfikatorów/multimediów na kody HID Usage.
#pragma once

#include <stdint.h>

namespace tap32 {

// Bity modyfikatorów w raporcie klawiatury HID.
enum HidMod : uint8_t {
  kModLCtrl = 0x01,
  kModLShift = 0x02,
  kModLAlt = 0x04,
  kModLGui = 0x08,
  kModRCtrl = 0x10,
  kModRShift = 0x20,
  kModRAlt = 0x40,
  kModRGui = 0x80,
};

// Kody Consumer Page (0x0C).
enum ConsumerUsage : uint16_t {
  kConsumerPlayPause = 0x00CD,
  kConsumerNext = 0x00B5,
  kConsumerPrev = 0x00B6,
  kConsumerStop = 0x00B7,
  kConsumerVolUp = 0x00E9,
  kConsumerVolDown = 0x00EA,
  kConsumerMute = 0x00E2,
};

// Zwraca kod HID (Keyboard page 0x07) lub 0, gdy nazwa jest nieznana.
uint8_t hidKeyFromName(const char* name);
// Zwraca bit modyfikatora lub 0.
uint8_t hidModFromName(const char* name);
// Zwraca kod Consumer Control lub 0.
uint16_t consumerFromName(const char* name);

}  // namespace tap32
