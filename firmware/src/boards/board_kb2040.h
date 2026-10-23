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

// Na PCB Tap32 SDA jest na GPIO3, a SCL na GPIO2 – odwrotnie niż sprzętowe I2C1 RP2040
// (GPIO2 może być tylko SDA, GPIO3 tylko SCL), dlatego ekran obsługuje programowe I²C.
constexpr uint8_t kSda = 3;  // D3
constexpr uint8_t kScl = 2;  // D2
constexpr bool kOledSoftI2c = true;

constexpr uint8_t kNeoPixelPin = 17;
constexpr uint8_t kNeoPixelBrightness = 24;  // niska jasność (0–255)

}  // namespace board
}  // namespace tap32
