#include "encoder.h"

#include <Arduino.h>

#include "boards/board.h"

namespace tap32 {

namespace {

volatile int32_t gPulses = 0;
volatile uint8_t gState = 3;
QuadDecoder gDecoder;

void TAP32_ISR_ATTR onEncoderEdge() {
  const uint8_t a = digitalRead(board::kEncA) == HIGH ? 1 : 0;
  const uint8_t b = digitalRead(board::kEncB) == HIGH ? 1 : 0;
  gPulses = gPulses + gDecoder.update(a, b);
  gState = gDecoder.state();
}

}  // namespace

void Encoder::begin() {
  pinMode(board::kEncA, INPUT_PULLUP);
  pinMode(board::kEncB, INPUT_PULLUP);
  delayMicroseconds(50);
  gDecoder.reset(digitalRead(board::kEncA) == HIGH, digitalRead(board::kEncB) == HIGH);
  gState = gDecoder.state();
  attachInterrupt(digitalPinToInterrupt(board::kEncA), onEncoderEdge, CHANGE);
  attachInterrupt(digitalPinToInterrupt(board::kEncB), onEncoderEdge, CHANGE);
}

void Encoder::setPulsesPerDetent(uint8_t pulses) { detents_.setPulsesPerDetent(pulses); }

int32_t Encoder::takeSteps() {
  noInterrupts();
  const int32_t pulses = gPulses;
  const uint8_t state = gState;
  interrupts();

  const int32_t delta = pulses - lastPulses_;
  lastPulses_ = pulses;
  const int32_t steps = detents_.feed(delta, state);
  return reverse_ ? -steps : steps;
}

int32_t Encoder::rawPulses() const { return gPulses; }

}  // namespace tap32
