#include "settings.h"

#include "config.h"
#include "hal/hal.h"

namespace tap32 {

namespace {
char gBuffer[kConfigBufSize];
}

bool ConfigStore::load(DeviceConfig& cfg) {
  cfg.setDefaults();
  if (!hal::storageBegin()) return false;
  const size_t n = hal::storageLoad(gBuffer, sizeof(gBuffer));
  if (n == 0) return false;
  return decodeConfig(gBuffer, n, cfg);
}

void ConfigStore::markDirty(uint32_t nowMs) {
  dirty_ = true;
  dirtySince_ = nowMs;
}

bool ConfigStore::update(const DeviceConfig& cfg, uint32_t nowMs) {
  if (!dirty_ || nowMs - dirtySince_ < kConfigSaveDelayMs) return false;
  return flush(cfg);
}

bool ConfigStore::flush(const DeviceConfig& cfg) {
  if (!dirty_) return true;
  dirty_ = false;
  const size_t n = encodeConfig(cfg, gBuffer, sizeof(gBuffer));
  if (n == 0) return false;
  return hal::storageSave(gBuffer, n);
}

}  // namespace tap32
