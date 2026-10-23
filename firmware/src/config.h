// Stałe kompilacji Tap32 wspólne dla obu płytek.
#pragma once

#include <stddef.h>
#include <stdint.h>

#ifndef TAP32_FW_VERSION
#define TAP32_FW_VERSION "1.0.0"
#endif

// Domyślny adres I²C wyświetlacza (nadpisywany ustawieniem oled_addr).
#ifndef TAP32_OLED_ADDR
#define TAP32_OLED_ADDR 0x3C
#endif

namespace tap32 {

constexpr uint32_t kScanIntervalUs = 1000;      // skan matrycy co 1 ms
constexpr uint32_t kRowSettleUs = 5;            // ustalenie po przełączeniu wiersza
constexpr uint32_t kEncReportIntervalMs = 10;   // agregacja zdarzeń enkodera
constexpr uint32_t kHeartbeatTimeoutMs = 3000;  // brak ping → offline
constexpr uint32_t kTestComboHoldMs = 3000;     // K1+K3 → tryb testu
constexpr uint32_t kTestComboBootWindowMs = 500;  // kombinacja musi być wciśnięta od startu
constexpr uint32_t kConfigSaveDelayMs = 3000;   // opóźniony zapis (oszczędzanie flash)
constexpr size_t kConfigBufSize = 1536;

}  // namespace tap32
