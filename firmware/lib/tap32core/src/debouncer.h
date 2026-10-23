// Debounce pojedynczego wejścia: stan jest akceptowany, gdy surowy odczyt jest stabilny
// przez debounce_ms. Czysta logika (czas podawany z zewnątrz).
#pragma once

#include <stdint.h>

namespace tap32 {

class Debouncer {
 public:
  // Zwraca true, jeśli ustabilizowany stan właśnie się zmienił.
  bool update(bool raw, uint32_t nowMs, uint8_t debounceMs) {
    if (raw != lastRaw_) {
      lastRaw_ = raw;
      changedAt_ = nowMs;
      return false;
    }
    if (raw != stable_ && static_cast<uint32_t>(nowMs - changedAt_) >= debounceMs) {
      stable_ = raw;
      return true;
    }
    return false;
  }

  bool pressed() const { return stable_; }

  void reset(bool state, uint32_t nowMs) {
    stable_ = lastRaw_ = state;
    changedAt_ = nowMs;
  }

 private:
  bool stable_ = false;
  bool lastRaw_ = false;
  uint32_t changedAt_ = 0;
};

}  // namespace tap32
