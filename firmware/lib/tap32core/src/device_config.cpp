#include "device_config.h"

#include <ArduinoJson.h>
#include <string.h>

#include "hid_codes.h"

namespace tap32 {

void copyUtf8(char* dst, size_t dstSize, const char* src, size_t maxChars) {
  if (dstSize == 0) return;
  size_t out = 0;
  size_t chars = 0;
  if (src != nullptr) {
    while (*src && chars < maxChars) {
      const uint8_t lead = static_cast<uint8_t>(*src);
      size_t seqLen = 1;
      if ((lead & 0xE0) == 0xC0) {
        seqLen = 2;
      } else if ((lead & 0xF0) == 0xE0) {
        seqLen = 3;
      } else if ((lead & 0xF8) == 0xF0) {
        seqLen = 4;
      }
      // Sprawdzenie, czy cała sekwencja istnieje i zmieści się w buforze.
      size_t i = 1;
      while (i < seqLen && src[i] != '\0') ++i;
      if (i < seqLen) break;
      if (out + seqLen >= dstSize) break;
      memcpy(dst + out, src, seqLen);
      out += seqLen;
      src += seqLen;
      ++chars;
    }
  }
  dst[out] = '\0';
}

void DeviceConfig::defaultFallback(FallbackBinding (&slots)[kFallbackSlots]) {
  for (FallbackBinding& b : slots) b = FallbackBinding();
  slots[kEncoderKey - 1].media = kConsumerMute;
  slots[kSlotEncCw].media = kConsumerVolUp;
  slots[kSlotEncCcw].media = kConsumerVolDown;
}

void DeviceConfig::setDefaults() {
  settings = Settings();
  defaultFallback(fallback);
  display = DisplayState();
}

size_t encodeConfig(const DeviceConfig& cfg, char* buf, size_t cap) {
  JsonDocument doc;
  doc["v"] = 1;
  JsonObject s = doc["settings"].to<JsonObject>();
  s["brightness"] = cfg.settings.brightness;
  s["screensaver_s"] = cfg.settings.screensaverS;
  s["flip"] = cfg.settings.flip;
  s["enc_reverse"] = cfg.settings.encReverse;
  s["enc_pulses"] = cfg.settings.encPulses;
  s["debounce_ms"] = cfg.settings.debounceMs;
  s["oled_addr"] = cfg.settings.oledAddr;

  JsonArray fb = doc["fallback"].to<JsonArray>();
  for (const FallbackBinding& b : cfg.fallback) {
    JsonArray item = fb.add<JsonArray>();
    item.add(b.mods);
    item.add(b.code);
    item.add(b.media);
  }

  JsonObject d = doc["display"].to<JsonObject>();
  d["mode"] = static_cast<uint8_t>(cfg.display.mode);
  d["title"] = cfg.display.title;
  JsonArray labels = d["labels"].to<JsonArray>();
  for (const auto& label : cfg.display.labels) labels.add(label);

  if (measureJson(doc) + 1 > cap) return 0;
  return serializeJson(doc, buf, cap);
}

bool decodeConfig(const char* json, size_t len, DeviceConfig& cfg) {
  cfg.setDefaults();
  JsonDocument doc;
  if (deserializeJson(doc, json, len) != DeserializationError::Ok) return false;
  JsonObjectConst root = doc.as<JsonObjectConst>();
  const int version = root["v"] | 0;
  if (version != 1) return false;

  JsonObjectConst s = root["settings"];
  Settings& st = cfg.settings;
  st.brightness = s["brightness"] | st.brightness;
  st.screensaverS = s["screensaver_s"] | st.screensaverS;
  st.flip = s["flip"] | st.flip;
  st.encReverse = s["enc_reverse"] | st.encReverse;
  st.encPulses = s["enc_pulses"] | st.encPulses;
  st.debounceMs = s["debounce_ms"] | st.debounceMs;
  st.oledAddr = s["oled_addr"] | st.oledAddr;
  if (st.encPulses < 1 || st.encPulses > 8) st.encPulses = 4;
  if (st.debounceMs < 1 || st.debounceMs > 50) st.debounceMs = 8;

  JsonArrayConst fb = root["fallback"];
  if (fb.size() == kFallbackSlots) {
    for (int i = 0; i < kFallbackSlots; ++i) {
      JsonArrayConst item = fb[i];
      cfg.fallback[i].mods = item[0] | 0;
      cfg.fallback[i].code = item[1] | 0;
      cfg.fallback[i].media = item[2] | 0;
    }
  }

  JsonObjectConst d = root["display"];
  const uint8_t mode = d["mode"] | 0;
  if (mode == static_cast<uint8_t>(DisplayMode::Profile) ||
      mode == static_cast<uint8_t>(DisplayMode::Grid)) {
    cfg.display.mode = static_cast<DisplayMode>(mode);
    copyUtf8(cfg.display.title, sizeof(cfg.display.title), d["title"] | "", kTitleChars);
    JsonArrayConst labels = d["labels"];
    for (int i = 0; i < kMatrixKeys; ++i) {
      copyUtf8(cfg.display.labels[i], kLabelBuf, labels[i] | "", kLabelChars);
    }
  }
  return true;
}

}  // namespace tap32
