#include "quad_decoder.h"

namespace tap32 {

// Indeks: (poprzedni stan << 2) | nowy stan, stan = A<<1 | B.
// Sekwencja 00→01→11→10→00 daje +1, odwrotna −1, brak zmiany i skok o 2 stany – 0.
const int8_t QuadDecoder::kTable[16] = {
    0,  +1, -1, 0,   // 00 → 00, 01, 10, 11
    -1, 0,  0,  +1,  // 01 → ...
    +1, 0,  0,  -1,  // 10 → ...
    0,  -1, +1, 0,   // 11 → ...
};

bool DetentCounter::isRestState(uint8_t quadState) const {
  // EC11 z 4 impulsami na ząbek spoczywa w stanie 11 (oba styki rozwarte, pull-up).
  // Przy 2 impulsach na ząbek pozycje spoczynkowe to 00 i 11.
  if (pulses_ == 4) return quadState == 3;
  if (pulses_ == 2) return quadState == 0 || quadState == 3;
  return false;
}

int32_t DetentCounter::feed(int32_t pulseDelta, uint8_t quadState) {
  acc_ += pulseDelta;
  int32_t steps = acc_ / pulses_;  // dzielenie w stronę zera
  acc_ -= steps * pulses_;

  if (acc_ != 0 && isRestState(quadState)) {
    // W spoczynku reszta powinna być zerem – zaokrąglamy do najbliższego ząbka.
    const int32_t half = (pulses_ + 1) / 2;
    if (acc_ >= half) {
      steps += 1;
    } else if (acc_ <= -half) {
      steps -= 1;
    }
    acc_ = 0;
  }
  return steps;
}

}  // namespace tap32
