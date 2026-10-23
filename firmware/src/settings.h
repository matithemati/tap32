// Trwała konfiguracja urządzenia (ustawienia, skróty trybu awaryjnego, ostatni ekran).
// Zapis jest opóźniony, żeby seria zmian nie zużywała pamięci flash.
#pragma once

#include <stdint.h>

#include "device_config.h"

namespace tap32 {

class ConfigStore {
 public:
  // Wczytuje konfigurację (lub wartości domyślne). Zwraca true, jeśli znaleziono zapis.
  bool load(DeviceConfig& cfg);
  void markDirty(uint32_t nowMs);
  // Zapisuje, jeśli od ostatniej zmiany minęło kConfigSaveDelayMs. Zwraca true po zapisie.
  bool update(const DeviceConfig& cfg, uint32_t nowMs);
  bool flush(const DeviceConfig& cfg);

 private:
  bool dirty_ = false;
  uint32_t dirtySince_ = 0;
};

}  // namespace tap32
