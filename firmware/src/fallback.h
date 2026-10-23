// Tryb awaryjny: gdy aplikacja nie odpowiada, klawisze i pokrętło wysyłają skróty HID.
#pragma once

#include <stdint.h>

#include "device_config.h"

namespace tap32 {

class Fallback {
 public:
  explicit Fallback(const FallbackBinding (&bindings)[kFallbackSlots]) : bindings_(bindings) {}

  // Wyłączenie zwalnia wszystkie wciśnięte klawisze HID.
  void setEnabled(bool enabled);
  bool enabled() const { return enabled_; }

  void onKey(uint8_t key, bool down);
  void onEncoder(int32_t steps);
  // Wysyła zakolejkowane raporty, gdy HID jest gotowy (jeden raport na wywołanie).
  void update();

 private:
  struct Report {
    bool consumer;
    uint8_t mods;
    uint8_t keys[6];
    uint16_t usage;
  };

  void pushKeyboardState(uint8_t extraMods, uint8_t extraCode);
  void pushConsumer(uint16_t usage);
  bool push(const Report& r);

  const FallbackBinding (&bindings_)[kFallbackSlots];
  bool enabled_ = true;
  uint16_t heldKeyboard_ = 0;  // bity klawiszy 1..10 trzymanych ze skrótem klawiaturowym
  uint16_t heldConsumerKey_ = 0;  // klawisz trzymający consumer control (0 = brak)
  bool anySent_ = false;

  static constexpr uint8_t kQueueSize = 32;
  Report queue_[kQueueSize];
  uint8_t head_ = 0;
  uint8_t count_ = 0;
};

}  // namespace tap32
