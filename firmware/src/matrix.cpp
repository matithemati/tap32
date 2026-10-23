#include "matrix.h"

#include <Arduino.h>

#include "boards/board.h"
#include "config.h"

namespace tap32 {

namespace {

// Wiersz nieaktywny = wejście (wysoka impedancja), dzięki temu nie ma zwarć między wierszami.
void releaseRow(uint8_t pin) { pinMode(pin, INPUT); }

void selectRow(uint8_t pin) {
  digitalWrite(pin, LOW);
  pinMode(pin, OUTPUT);
}

}  // namespace

void Matrix::begin() {
  for (uint8_t pin : board::kRowPins) releaseRow(pin);
  for (uint8_t pin : board::kColPins) pinMode(pin, INPUT_PULLUP);
  pinMode(board::kEncSw, INPUT_PULLUP);
  const uint32_t now = millis();
  for (Debouncer& d : keys_) d.reset(false, now);
}

void Matrix::scan(uint32_t nowMs, uint8_t debounceMs, KeyCallback onChange) {
  for (uint8_t r = 0; r < 3; ++r) {
    selectRow(board::kRowPins[r]);
    delayMicroseconds(kRowSettleUs);
    for (uint8_t c = 0; c < 3; ++c) {
      const bool raw = digitalRead(board::kColPins[c]) == LOW;
      const uint8_t index = static_cast<uint8_t>(r * 3 + c);
      if (keys_[index].update(raw, nowMs, debounceMs) && onChange != nullptr) {
        onChange(static_cast<uint8_t>(index + 1), keys_[index].pressed());
      }
    }
    releaseRow(board::kRowPins[r]);
  }

  // Przycisk enkodera – ten sam debounce co matryca.
  const bool rawSw = digitalRead(board::kEncSw) == LOW;
  Debouncer& sw = keys_[kEncoderKey - 1];
  if (sw.update(rawSw, nowMs, debounceMs) && onChange != nullptr) {
    onChange(kEncoderKey, sw.pressed());
  }
}

bool Matrix::pressed(uint8_t key) const {
  if (key < 1 || key > kTotalKeys) return false;
  return keys_[key - 1].pressed();
}

}  // namespace tap32
