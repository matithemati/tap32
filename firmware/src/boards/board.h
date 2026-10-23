// Wybór mapy pinów płytki na podstawie flagi budowania (platformio.ini).
// Każdy plik board_*.h definiuje w przestrzeni nazw tap32::board te same stałe:
//   kBoardId, kBoardName, kRowPins[3], kColPins[3], kEncA, kEncB, kEncSw, kSda, kScl
// oraz makro TAP32_ISR_ATTR (atrybut funkcji obsługi przerwań).
#pragma once

#if defined(TAP32_BOARD_KB2040)
#include "board_kb2040.h"
#elif defined(TAP32_BOARD_XIAO_ESP32S3)
#include "board_xiao_esp32s3.h"
#else
#error "Nie wybrano płytki: zdefiniuj TAP32_BOARD_KB2040 lub TAP32_BOARD_XIAO_ESP32S3"
#endif
