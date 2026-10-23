#include "fallback.h"

#include <string.h>

#include "hal/hal.h"

namespace tap32 {

namespace {
constexpr int32_t kMaxEncoderBurst = 10;
}

void Fallback::setEnabled(bool enabled) {
  if (enabled_ == enabled) return;
  enabled_ = enabled;
  if (!enabled) {
    // Zwolnienie wszystkiego, co mogło zostać wciśnięte (żadnych „zawieszonych” klawiszy).
    heldKeyboard_ = 0;
    heldConsumerKey_ = 0;
    count_ = 0;
    if (anySent_) {
      pushKeyboardState(0, 0);
      pushConsumer(0);
      anySent_ = false;
    }
  }
}

bool Fallback::push(const Report& r) {
  if (count_ >= kQueueSize) return false;
  queue_[(head_ + count_) % kQueueSize] = r;
  ++count_;
  return true;
}

void Fallback::pushKeyboardState(uint8_t extraMods, uint8_t extraCode) {
  Report r;
  memset(&r, 0, sizeof(r));
  r.consumer = false;
  uint8_t n = 0;
  auto addCode = [&](uint8_t code) {
    if (code == 0 || n >= 6) return;
    for (uint8_t i = 0; i < n; ++i) {
      if (r.keys[i] == code) return;
    }
    r.keys[n++] = code;
  };
  for (uint8_t i = 0; i < kTotalKeys; ++i) {
    if (heldKeyboard_ & (1u << i)) {
      r.mods |= bindings_[i].mods;
      addCode(bindings_[i].code);
    }
  }
  r.mods |= extraMods;
  addCode(extraCode);
  push(r);
}

void Fallback::pushConsumer(uint16_t usage) {
  Report r;
  memset(&r, 0, sizeof(r));
  r.consumer = true;
  r.usage = usage;
  push(r);
}

void Fallback::onKey(uint8_t key, bool down) {
  if (!enabled_ || key < 1 || key > kTotalKeys) return;
  const FallbackBinding& b = bindings_[key - 1];
  const uint16_t bit = static_cast<uint16_t>(1u << (key - 1));

  if (down) {
    if (b.media != 0) {
      heldConsumerKey_ = key;
      pushConsumer(b.media);
      anySent_ = true;
    } else if (b.mods != 0 || b.code != 0) {
      heldKeyboard_ |= bit;
      pushKeyboardState(0, 0);
      anySent_ = true;
    }
    return;
  }

  if (heldConsumerKey_ == key) {
    heldConsumerKey_ = 0;
    pushConsumer(0);
  }
  if (heldKeyboard_ & bit) {
    heldKeyboard_ &= static_cast<uint16_t>(~bit);
    pushKeyboardState(0, 0);
  }
}

void Fallback::onEncoder(int32_t steps) {
  if (!enabled_ || steps == 0) return;
  const FallbackBinding& b = bindings_[steps > 0 ? kSlotEncCw : kSlotEncCcw];
  if (b.empty()) return;
  int32_t n = steps > 0 ? steps : -steps;
  if (n > kMaxEncoderBurst) n = kMaxEncoderBurst;
  for (int32_t i = 0; i < n; ++i) {
    if (b.media != 0) {
      pushConsumer(b.media);
      pushConsumer(0);
    } else {
      pushKeyboardState(b.mods, b.code);
      pushKeyboardState(0, 0);
    }
  }
  anySent_ = true;
}

void Fallback::update() {
  if (count_ == 0 || !hal::hidReady()) return;
  const Report& r = queue_[head_];
  if (r.consumer) {
    hal::hidConsumerReport(r.usage);
  } else {
    hal::hidKeyboardReport(r.mods, r.keys);
  }
  head_ = static_cast<uint8_t>((head_ + 1) % kQueueSize);
  --count_;
}

}  // namespace tap32
