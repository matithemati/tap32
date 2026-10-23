#include "hid_codes.h"

#include <stdlib.h>
#include <string.h>

namespace tap32 {

namespace {

struct NamedKey {
  const char* name;
  uint8_t code;
};

const NamedKey kNamedKeys[] = {
    {"enter", 0x28},     {"return", 0x28},     {"esc", 0x29},        {"escape", 0x29},
    {"backspace", 0x2A}, {"tab", 0x2B},        {"space", 0x2C},      {"minus", 0x2D},
    {"equal", 0x2E},     {"lbracket", 0x2F},   {"rbracket", 0x30},   {"backslash", 0x31},
    {"semicolon", 0x33}, {"quote", 0x34},      {"grave", 0x35},      {"comma", 0x36},
    {"period", 0x37},    {"slash", 0x38},      {"capslock", 0x39},   {"printscreen", 0x46},
    {"scrolllock", 0x47}, {"pause", 0x48},     {"insert", 0x49},     {"home", 0x4A},
    {"pageup", 0x4B},    {"delete", 0x4C},     {"end", 0x4D},        {"pagedown", 0x4E},
    {"right", 0x4F},     {"left", 0x50},       {"down", 0x51},       {"up", 0x52},
    {"numlock", 0x53},   {"kp_divide", 0x54},  {"kp_multiply", 0x55}, {"kp_minus", 0x56},
    {"kp_plus", 0x57},   {"kp_enter", 0x58},   {"kp_period", 0x63},  {"menu", 0x65},
    {"-", 0x2D},         {"=", 0x2E},          {"[", 0x2F},          {"]", 0x30},
    {"\\", 0x31},        {";", 0x33},          {"'", 0x34},          {"`", 0x35},
    {",", 0x36},         {".", 0x37},          {"/", 0x38},
};

struct NamedMod {
  const char* name;
  uint8_t bit;
};

const NamedMod kNamedMods[] = {
    {"ctrl", kModLCtrl},   {"control", kModLCtrl}, {"shift", kModLShift}, {"alt", kModLAlt},
    {"win", kModLGui},     {"gui", kModLGui},      {"meta", kModLGui},    {"cmd", kModLGui},
    {"lctrl", kModLCtrl},  {"lshift", kModLShift}, {"lalt", kModLAlt},    {"lwin", kModLGui},
    {"rctrl", kModRCtrl},  {"rshift", kModRShift}, {"ralt", kModRAlt},    {"altgr", kModRAlt},
    {"rwin", kModRGui},    {"rgui", kModRGui},
};

struct NamedConsumer {
  const char* name;
  uint16_t usage;
};

const NamedConsumer kNamedConsumers[] = {
    {"play_pause", kConsumerPlayPause}, {"next", kConsumerNext},
    {"prev", kConsumerPrev},            {"stop", kConsumerStop},
    {"vol_up", kConsumerVolUp},         {"vol_down", kConsumerVolDown},
    {"mute", kConsumerMute},
};

// Porównanie bez rozróżniania wielkości liter (tylko ASCII).
bool equalsIgnoreCase(const char* a, const char* b) {
  while (*a && *b) {
    char ca = *a, cb = *b;
    if (ca >= 'A' && ca <= 'Z') ca = static_cast<char>(ca - 'A' + 'a');
    if (cb >= 'A' && cb <= 'Z') cb = static_cast<char>(cb - 'A' + 'a');
    if (ca != cb) return false;
    ++a;
    ++b;
  }
  return *a == *b;
}

// Parsuje liczbę dziesiętną z całego napisu; zwraca −1 przy błędzie.
int parseNumber(const char* s) {
  if (*s == '\0') return -1;
  int value = 0;
  for (; *s; ++s) {
    if (*s < '0' || *s > '9') return -1;
    value = value * 10 + (*s - '0');
    if (value > 1000) return -1;
  }
  return value;
}

}  // namespace

uint8_t hidKeyFromName(const char* name) {
  if (name == nullptr || *name == '\0') return 0;
  const size_t len = strlen(name);

  if (len == 1) {
    char c = name[0];
    if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    if (c >= 'a' && c <= 'z') return static_cast<uint8_t>(0x04 + (c - 'a'));
    if (c >= '1' && c <= '9') return static_cast<uint8_t>(0x1E + (c - '1'));
    if (c == '0') return 0x27;
  }

  // f1..f24
  if ((name[0] == 'f' || name[0] == 'F') && len >= 2 && len <= 3) {
    const int n = parseNumber(name + 1);
    if (n >= 1 && n <= 12) return static_cast<uint8_t>(0x3A + (n - 1));
    if (n >= 13 && n <= 24) return static_cast<uint8_t>(0x68 + (n - 13));
  }

  // kp_0..kp_9
  if (len == 4 && (strncmp(name, "kp_", 3) == 0 || strncmp(name, "KP_", 3) == 0)) {
    const char d = name[3];
    if (d == '0') return 0x62;
    if (d >= '1' && d <= '9') return static_cast<uint8_t>(0x59 + (d - '1'));
  }

  for (const NamedKey& k : kNamedKeys) {
    if (equalsIgnoreCase(name, k.name)) return k.code;
  }
  return 0;
}

uint8_t hidModFromName(const char* name) {
  if (name == nullptr) return 0;
  for (const NamedMod& m : kNamedMods) {
    if (equalsIgnoreCase(name, m.name)) return m.bit;
  }
  return 0;
}

uint16_t consumerFromName(const char* name) {
  if (name == nullptr) return 0;
  for (const NamedConsumer& c : kNamedConsumers) {
    if (equalsIgnoreCase(name, c.name)) return c.usage;
  }
  return 0;
}

}  // namespace tap32
