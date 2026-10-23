// Dekoder enkodera kwadraturowego (kod Graya) odporny na drgania styków.
// Czysta logika bez zależności od Arduino – testowana w środowisku native.
#pragma once

#include <stdint.h>

namespace tap32 {

// Liczy impulsy (zmiany stanu A/B). Każde przejście do sąsiedniego stanu kodu Graya
// daje ±1, przejście niedozwolone (zmiana obu linii naraz) daje 0. Drgania styku
// generują pary +1/−1, które się znoszą.
class QuadDecoder {
 public:
  // Ustawia stan początkowy bez liczenia impulsu.
  void reset(uint8_t a, uint8_t b) {
    state_ = static_cast<uint8_t>(((a ? 1 : 0) << 1) | (b ? 1 : 0));
  }

  // Wywoływane z przerwania przy każdej zmianie A lub B. Zwraca −1, 0 lub +1.
  int8_t update(uint8_t a, uint8_t b) {
    const uint8_t next = static_cast<uint8_t>(((a ? 1 : 0) << 1) | (b ? 1 : 0));
    const int8_t delta = kTable[(state_ << 2) | next];
    state_ = next;
    return delta;
  }

  uint8_t state() const { return state_; }

 private:
  static const int8_t kTable[16];
  uint8_t state_ = 3;
};

// Przelicza impulsy na ząbki (detenty) według liczby impulsów na ząbek.
// Resztę zachowuje między wywołaniami; w pozycji spoczynkowej resynchronizuje
// licznik, żeby zgubione impulsy nie przesuwały momentu zgłoszenia kroku.
class DetentCounter {
 public:
  void setPulsesPerDetent(uint8_t pulses) {
    pulses_ = pulses == 0 ? 1 : pulses;
    acc_ = 0;
  }
  uint8_t pulsesPerDetent() const { return pulses_; }

  // pulseDelta – suma impulsów od ostatniego wywołania, quadState – aktualny stan (A<<1|B).
  // Zwraca liczbę pełnych ząbków (ze znakiem).
  int32_t feed(int32_t pulseDelta, uint8_t quadState);

  void clear() { acc_ = 0; }

 private:
  bool isRestState(uint8_t quadState) const;

  int32_t acc_ = 0;
  uint8_t pulses_ = 4;
};

}  // namespace tap32
