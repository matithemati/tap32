// Enkoder EC11: przerwania na A i B (CHANGE) + dekoder kodu Graya z lib/tap32core.
#pragma once

#include <stdint.h>

#include "quad_decoder.h"

namespace tap32 {

class Encoder {
 public:
  void begin();
  void setPulsesPerDetent(uint8_t pulses);
  void setReverse(bool reverse) { reverse_ = reverse; }

  // Zwraca liczbę ząbków od ostatniego wywołania (+ = CW, uwzględnia odwrócenie).
  int32_t takeSteps();
  // Surowy licznik impulsów (tryb testu).
  int32_t rawPulses() const;

 private:
  DetentCounter detents_;
  int32_t lastPulses_ = 0;
  bool reverse_ = false;
};

}  // namespace tap32
