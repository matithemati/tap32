#include "protocol_codec.h"

#include <ArduinoJson.h>
#include <string.h>

#include "hid_codes.h"

namespace tap32 {

namespace {

constexpr uint32_t kMaxDisplayMs = 600000;
constexpr uint32_t kMaxFlashMs = 10000;

ParseResult invalid(const char* msg) { return ParseResult{ParseStatus::Invalid, msg}; }
ParseResult ok() { return ParseResult{ParseStatus::Ok, nullptr}; }

// Pobiera opcjonalny napis. Zwraca false (i ustawia err), gdy pole ma zły typ.
bool readString(JsonObjectConst obj, const char* key, char* dst, size_t cap, size_t maxChars,
                const char*& err) {
  JsonVariantConst v = obj[key];
  if (v.isNull()) return true;
  if (!v.is<const char*>()) {
    err = "string expected";
    return false;
  }
  copyUtf8(dst, cap, v.as<const char*>(), maxChars);
  return true;
}

// Pobiera opcjonalną liczbę całkowitą z zakresu [lo, hi].
bool readInt(JsonObjectConst obj, const char* key, int32_t lo, int32_t hi, int32_t& out,
             bool& present, const char*& err) {
  JsonVariantConst v = obj[key];
  present = false;
  if (v.isNull()) return true;
  if (!v.is<int32_t>()) {
    err = "integer expected";
    return false;
  }
  const int32_t value = v.as<int32_t>();
  if (value < lo || value > hi) {
    err = "value out of range";
    return false;
  }
  out = value;
  present = true;
  return true;
}

bool readBool(JsonObjectConst obj, const char* key, bool& out, bool& present, const char*& err) {
  JsonVariantConst v = obj[key];
  present = false;
  if (v.isNull()) return true;
  if (!v.is<bool>()) {
    err = "boolean expected";
    return false;
  }
  out = v.as<bool>();
  present = true;
  return true;
}

ParseResult parseDisplay(JsonObjectConst obj, DisplayCommand& d) {
  const char* mode = obj["mode"];
  if (mode == nullptr) return invalid("missing mode");
  const char* err = nullptr;
  int32_t value = 0;
  bool present = false;

  if (strcmp(mode, "profile") == 0) {
    d.mode = DisplayMode::Profile;
    if (!readString(obj, "name", d.title, sizeof(d.title), kTitleChars, err)) return invalid(err);
    return ok();
  }
  if (strcmp(mode, "grid") == 0) {
    d.mode = DisplayMode::Grid;
    if (!readString(obj, "title", d.title, sizeof(d.title), kTitleChars, err)) return invalid(err);
    JsonVariantConst labels = obj["labels"];
    if (!labels.isNull()) {
      if (!labels.is<JsonArrayConst>()) return invalid("labels must be an array");
      JsonArrayConst arr = labels.as<JsonArrayConst>();
      if (arr.size() > kMatrixKeys) return invalid("too many labels");
      for (size_t i = 0; i < arr.size(); ++i) {
        JsonVariantConst item = arr[i];
        if (item.isNull()) continue;
        if (!item.is<const char*>()) return invalid("label must be a string");
        copyUtf8(d.labels[i], kLabelBuf, item.as<const char*>(), kLabelChars);
      }
    }
    return ok();
  }
  if (strcmp(mode, "text") == 0) {
    d.mode = DisplayMode::Text;
    if (!readString(obj, "line1", d.line1, sizeof(d.line1), kTitleChars, err)) return invalid(err);
    if (!readString(obj, "line2", d.line2, sizeof(d.line2), kTitleChars, err)) return invalid(err);
  } else if (strcmp(mode, "bar") == 0) {
    d.mode = DisplayMode::Bar;
    if (!readString(obj, "title", d.title, sizeof(d.title), kTitleChars, err)) return invalid(err);
    JsonVariantConst v = obj["value"];
    if (!v.isNull()) {
      if (!v.is<int32_t>()) return invalid("integer expected");
      int32_t raw = v.as<int32_t>();
      if (raw < 0) raw = 0;
      if (raw > 100) raw = 100;
      d.value = static_cast<uint8_t>(raw);
    }
  } else {
    return invalid("unknown display mode");
  }

  if (!readInt(obj, "ms", 0, static_cast<int32_t>(kMaxDisplayMs), value, present, err)) {
    return invalid(err);
  }
  d.ms = present ? static_cast<uint32_t>(value) : 0;
  return ok();
}

ParseResult parseFlash(JsonObjectConst obj, FlashCommand& f) {
  const char* err = nullptr;
  int32_t value = 0;
  bool present = false;
  if (!obj["text"].is<const char*>()) return invalid("missing text");
  copyUtf8(f.text, sizeof(f.text), obj["text"].as<const char*>(), kTitleChars);
  if (!readInt(obj, "key", 1, kTotalKeys, value, present, err)) return invalid(err);
  f.key = present ? static_cast<uint8_t>(value) : 0;
  if (!readInt(obj, "ms", 1, static_cast<int32_t>(kMaxFlashMs), value, present, err)) {
    return invalid(err);
  }
  f.ms = present ? static_cast<uint32_t>(value) : 1000;
  return ok();
}

ParseResult parseSettings(JsonObjectConst obj, SettingsPatch& p) {
  const char* err = nullptr;
  int32_t value = 0;
  bool present = false;
  bool flag = false;

  if (!readInt(obj, "brightness", 0, 255, value, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kBrightness;
    p.values.brightness = static_cast<uint8_t>(value);
  }
  if (!readInt(obj, "screensaver_s", 0, 65535, value, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kScreensaver;
    p.values.screensaverS = static_cast<uint16_t>(value);
  }
  if (!readBool(obj, "flip", flag, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kFlip;
    p.values.flip = flag;
  }
  if (!readBool(obj, "enc_reverse", flag, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kEncReverse;
    p.values.encReverse = flag;
  }
  if (!readInt(obj, "enc_pulses", 1, 8, value, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kEncPulses;
    p.values.encPulses = static_cast<uint8_t>(value);
  }
  if (!readInt(obj, "debounce_ms", 1, 50, value, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kDebounce;
    p.values.debounceMs = static_cast<uint8_t>(value);
  }
  if (!readInt(obj, "oled_addr", 0x08, 0x77, value, present, err)) return invalid(err);
  if (present) {
    p.mask |= SettingsPatch::kOledAddr;
    p.values.oledAddr = static_cast<uint8_t>(value);
  }
  return ok();
}

ParseResult parseBinding(JsonObjectConst obj, uint8_t& slot, FallbackBinding& b) {
  JsonVariantConst key = obj["key"];
  if (key.is<int32_t>()) {
    const int32_t k = key.as<int32_t>();
    if (k < 1 || k > kTotalKeys) return invalid("key out of range");
    slot = static_cast<uint8_t>(k - 1);
  } else if (key.is<const char*>()) {
    const char* name = key.as<const char*>();
    if (strcmp(name, "enc_cw") == 0) {
      slot = kSlotEncCw;
    } else if (strcmp(name, "enc_ccw") == 0) {
      slot = kSlotEncCcw;
    } else {
      return invalid("unknown key");
    }
  } else {
    return invalid("missing key");
  }

  b = FallbackBinding();
  JsonVariantConst mods = obj["mods"];
  if (mods.is<const char*>()) {
    const uint8_t bit = hidModFromName(mods.as<const char*>());
    if (bit == 0) return invalid("unknown modifier");
    b.mods = bit;
  } else if (mods.is<JsonArrayConst>()) {
    for (JsonVariantConst m : mods.as<JsonArrayConst>()) {
      const uint8_t bit = hidModFromName(m.as<const char*>());
      if (bit == 0) return invalid("unknown modifier");
      b.mods |= bit;
    }
  } else if (!mods.isNull()) {
    return invalid("mods must be an array");
  }

  JsonVariantConst code = obj["code"];
  if (code.is<const char*>()) {
    b.code = hidKeyFromName(code.as<const char*>());
    if (b.code == 0) return invalid("unknown key code");
  } else if (code.is<int32_t>()) {
    const int32_t c = code.as<int32_t>();
    if (c < 1 || c > 255) return invalid("code out of range");
    b.code = static_cast<uint8_t>(c);
  } else if (!code.isNull()) {
    return invalid("bad code");
  }

  JsonVariantConst media = obj["media"];
  if (media.is<const char*>()) {
    b.media = consumerFromName(media.as<const char*>());
    if (b.media == 0) return invalid("unknown media key");
  } else if (media.is<int32_t>()) {
    const int32_t m = media.as<int32_t>();
    if (m < 1 || m > 0x3FF) return invalid("media out of range");
    b.media = static_cast<uint16_t>(m);
  } else if (!media.isNull()) {
    return invalid("bad media");
  }

  if (b.media != 0 && (b.code != 0 || b.mods != 0)) return invalid("use either code or media");
  return ok();
}

ParseResult parseFallback(JsonObjectConst obj, FallbackPatch& p) {
  JsonVariantConst replace = obj["replace"];
  if (!replace.isNull()) {
    if (!replace.is<bool>()) return invalid("boolean expected");
    p.replace = replace.as<bool>();
  }

  JsonVariantConst bindings = obj["bindings"];
  if (!bindings.isNull()) {
    if (!bindings.is<JsonArrayConst>()) return invalid("bindings must be an array");
    JsonArrayConst arr = bindings.as<JsonArrayConst>();
    if (arr.size() > kFallbackSlots) return invalid("too many bindings");
    for (JsonVariantConst item : arr) {
      if (!item.is<JsonObjectConst>()) return invalid("binding must be an object");
      ParseResult r = parseBinding(item.as<JsonObjectConst>(), p.slots[p.count],
                                   p.bindings[p.count]);
      if (r.status != ParseStatus::Ok) return r;
      ++p.count;
    }
    return ok();
  }

  if (!obj["key"].isNull()) {
    ParseResult r = parseBinding(obj, p.slots[0], p.bindings[0]);
    if (r.status != ParseStatus::Ok) return r;
    p.count = 1;
    return ok();
  }

  if (!p.replace) return invalid("missing key or bindings");
  return ok();
}

ParseResult parseFlag(JsonObjectConst obj, const char* key, bool defaultValue, bool& out) {
  JsonVariantConst v = obj[key];
  if (v.isNull()) {
    out = defaultValue;
    return ok();
  }
  if (!v.is<bool>()) return invalid("boolean expected");
  out = v.as<bool>();
  return ok();
}

size_t finish(JsonDocument& doc, char* buf, size_t cap) {
  if (measureJson(doc) + 1 > cap) return 0;
  return serializeJson(doc, buf, cap);
}

}  // namespace

void SettingsPatch::applyTo(Settings& s) const {
  if (mask & kBrightness) s.brightness = values.brightness;
  if (mask & kScreensaver) s.screensaverS = values.screensaverS;
  if (mask & kFlip) s.flip = values.flip;
  if (mask & kEncReverse) s.encReverse = values.encReverse;
  if (mask & kEncPulses) s.encPulses = values.encPulses;
  if (mask & kDebounce) s.debounceMs = values.debounceMs;
  if (mask & kOledAddr) s.oledAddr = values.oledAddr;
}

void FallbackPatch::applyTo(FallbackBinding (&target)[kFallbackSlots]) const {
  if (replace) {
    for (FallbackBinding& b : target) b = FallbackBinding();
  }
  for (uint8_t i = 0; i < count; ++i) target[slots[i]] = bindings[i];
}

ParseResult parseCommand(const char* line, size_t len, Command& out) {
  out = Command();
  JsonDocument doc;
  if (deserializeJson(doc, line, len) != DeserializationError::Ok) {
    return ParseResult{ParseStatus::BadJson, "invalid json"};
  }
  if (!doc.is<JsonObjectConst>()) return ParseResult{ParseStatus::BadJson, "object expected"};
  JsonObjectConst obj = doc.as<JsonObjectConst>();

  const char* type = obj["type"];
  if (type == nullptr) return ParseResult{ParseStatus::BadJson, "missing type"};

  JsonVariantConst id = obj["id"];
  if (!id.isNull()) {
    if (!id.is<int32_t>()) return invalid("id must be an integer");
    out.hasId = true;
    out.id = id.as<int32_t>();
  }

  if (strcmp(type, "hello") == 0) {
    out.type = CommandType::Hello;
    return ok();
  }
  if (strcmp(type, "ping") == 0) {
    out.type = CommandType::Ping;
    return ok();
  }
  if (strcmp(type, "get_info") == 0) {
    out.type = CommandType::GetInfo;
    return ok();
  }
  if (strcmp(type, "display") == 0) {
    out.type = CommandType::Display;
    return parseDisplay(obj, out.display);
  }
  if (strcmp(type, "flash") == 0) {
    out.type = CommandType::Flash;
    return parseFlash(obj, out.flash);
  }
  if (strcmp(type, "settings") == 0) {
    out.type = CommandType::Settings;
    return parseSettings(obj, out.settings);
  }
  if (strcmp(type, "set_fallback") == 0) {
    out.type = CommandType::SetFallback;
    return parseFallback(obj, out.fallback);
  }
  if (strcmp(type, "reboot") == 0) {
    out.type = CommandType::Reboot;
    return parseFlag(obj, "bootloader", false, out.flag);
  }
  if (strcmp(type, "test_mode") == 0) {
    out.type = CommandType::TestMode;
    return parseFlag(obj, "enable", true, out.flag);
  }
  if (strcmp(type, "debug") == 0) {
    out.type = CommandType::Debug;
    return parseFlag(obj, "enable", true, out.flag);
  }
  out.type = CommandType::Unknown;
  return ParseResult{ParseStatus::Ignored, nullptr};
}

size_t buildHello(char* buf, size_t cap, const char* board, const char* fw, bool online,
                  const I2cDiag* diag) {
  JsonDocument doc;
  doc["type"] = "hello";
  doc["device"] = "tap32";
  doc["fw"] = fw;
  doc["board"] = board;
  doc["keys"] = kTotalKeys;
  doc["encoder"] = true;
  doc["hid"] = true;
  doc["online"] = online;
  if (diag != nullptr) {
    if (diag->oledAddr != 0) {
      doc["oled"] = diag->oledAddr;
    } else {
      doc["oled"] = nullptr;  // ekran nie odpowiada
    }
    JsonArray devices = doc["i2c"].to<JsonArray>();
    for (uint8_t i = 0; i < diag->count && i < sizeof(diag->devices); ++i) {
      devices.add(diag->devices[i]);
    }
    if (diag->sdaLevel >= 0 && diag->sclLevel >= 0) {
      JsonObject lines = doc["lines"].to<JsonObject>();
      lines["sda"] = diag->sdaLevel;
      lines["scl"] = diag->sclLevel;
    }
    if (diag->swapped) doc["swapped"] = true;
  }
  return finish(doc, buf, cap);
}

size_t buildKey(char* buf, size_t cap, uint8_t key, bool down, uint32_t t) {
  JsonDocument doc;
  doc["type"] = "key";
  doc["key"] = key;
  doc["action"] = down ? "down" : "up";
  doc["t"] = t;
  return finish(doc, buf, cap);
}

size_t buildEnc(char* buf, size_t cap, int32_t steps, uint32_t t) {
  JsonDocument doc;
  doc["type"] = "enc";
  doc["steps"] = steps;
  doc["t"] = t;
  return finish(doc, buf, cap);
}

size_t buildAck(char* buf, size_t cap, int32_t id) {
  JsonDocument doc;
  doc["type"] = "ack";
  doc["id"] = id;
  return finish(doc, buf, cap);
}

size_t buildError(char* buf, size_t cap, bool hasId, int32_t id, const char* msg) {
  JsonDocument doc;
  doc["type"] = "error";
  if (hasId) doc["id"] = id;
  doc["msg"] = msg;
  return finish(doc, buf, cap);
}

size_t buildLog(char* buf, size_t cap, const char* level, const char* msg) {
  JsonDocument doc;
  doc["type"] = "log";
  doc["level"] = level;
  doc["msg"] = msg;
  return finish(doc, buf, cap);
}

size_t buildTest(char* buf, size_t cap, bool active) {
  JsonDocument doc;
  doc["type"] = "test";
  doc["active"] = active;
  return finish(doc, buf, cap);
}

}  // namespace tap32
