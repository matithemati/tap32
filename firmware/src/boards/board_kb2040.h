// Mapa pinów: Adafruit KB2040 (RP2040). Patrz docs/WIRING.md.
#pragma once

#include <stdint.h>

#define TAP32_ISR_ATTR

namespace tap32 {
namespace board {

constexpr const char* kBoardId = "kb2040";
constexpr const char* kBoardName = "KB2040";

constexpr uint8_t kRowPins[3] = {9, 8, 7};  // D9, D8, D7
constexpr uint8_t kColPins[3] = {6, 5, 4};  // D6, D5, D4

constexpr uint8_t kEncA = 19;   // MOSI
constexpr uint8_t kEncB = 20;   // MISO
constexpr uint8_t kEncSw = 18;  // SCK

constexpr uint8_t kSda = 0;  // I2C0 SDA (D0)
constexpr uint8_t kScl = 1;  // I2C0 SCL (D1)

constexpr uint8_t kNeoPixelPin = 17;
constexpr uint8_t kNeoPixelBrightness = 24;  // niska jasność (0–255)

}  // namespace board
}  // namespace tap32
