// Mapa pinów: Seeed Studio XIAO ESP32-S3. Patrz docs/WIRING.md.
// Wszystkie 11 pinów D0–D10 są zajęte. Nie inicjalizujemy Serial0 (UART0 na D6/D7).
#pragma once

#include <Arduino.h>
#include <stdint.h>

#define TAP32_ISR_ATTR ARDUINO_ISR_ATTR

namespace tap32 {
namespace board {

constexpr const char* kBoardId = "xiao_esp32s3";
constexpr const char* kBoardName = "XIAO ESP32-S3";

constexpr uint8_t kRowPins[3] = {7, 8, 9};    // D8, D9, D10
constexpr uint8_t kColPins[3] = {3, 43, 44};  // D2 (strapping), D6 (U0TX), D7 (U0RX)

constexpr uint8_t kEncA = 1;   // D0
constexpr uint8_t kEncB = 2;   // D1
constexpr uint8_t kEncSw = 4;  // D3

constexpr uint8_t kSda = 5;  // D4
constexpr uint8_t kScl = 6;  // D5

constexpr uint8_t kLedPin = 21;  // wbudowana dioda użytkownika
constexpr bool kLedActiveLow = true;

}  // namespace board
}  // namespace tap32
