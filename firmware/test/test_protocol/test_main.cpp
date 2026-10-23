// Testy parsera protokołu, budowania wiadomości, kodów HID i zapisu konfiguracji.
#include <string.h>
#include <unity.h>

#include "debouncer.h"
#include "device_config.h"
#include "hid_codes.h"
#include "protocol_codec.h"

using namespace tap32;

namespace {

Command cmd;

ParseResult parse(const char* line) { return parseCommand(line, strlen(line), cmd); }

}  // namespace

void setUp() {}
void tearDown() {}

void test_invalid_json() {
  ParseResult r = parse("{not json");
  TEST_ASSERT_EQUAL(ParseStatus::BadJson, r.status);
  TEST_ASSERT_NOT_NULL(r.error);
  r = parse("[1,2]");
  TEST_ASSERT_EQUAL(ParseStatus::BadJson, r.status);
  r = parse("{\"id\":1}");
  TEST_ASSERT_EQUAL(ParseStatus::BadJson, r.status);
}

void test_unknown_type_is_ignored() {
  ParseResult r = parse("{\"type\":\"future_thing\",\"id\":5,\"x\":1}");
  TEST_ASSERT_EQUAL(ParseStatus::Ignored, r.status);
}

void test_ping_with_id_and_unknown_fields() {
  ParseResult r = parse("{\"type\":\"ping\",\"id\":42,\"extra\":{\"a\":[1,2]}}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL(CommandType::Ping, cmd.type);
  TEST_ASSERT_TRUE(cmd.hasId);
  TEST_ASSERT_EQUAL_INT32(42, cmd.id);
}

void test_hello_without_id() {
  ParseResult r = parse("{\"type\":\"hello\",\"app\":\"1.0.0\"}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL(CommandType::Hello, cmd.type);
  TEST_ASSERT_FALSE(cmd.hasId);
}

void test_display_grid() {
  ParseResult r = parse(
      "{\"type\":\"display\",\"mode\":\"grid\",\"title\":\"Domyslny\","
      "\"labels\":[\"Calc\",\"Notatnik123\",null,\"WWW\"]}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL(DisplayMode::Grid, cmd.display.mode);
  TEST_ASSERT_EQUAL_STRING("Domyslny", cmd.display.title);
  TEST_ASSERT_EQUAL_STRING("Calc", cmd.display.labels[0]);
  TEST_ASSERT_EQUAL_STRING("Notatni", cmd.display.labels[1]);  // obcięte do 7 znaków
  TEST_ASSERT_EQUAL_STRING("", cmd.display.labels[2]);
  TEST_ASSERT_EQUAL_STRING("WWW", cmd.display.labels[3]);
  TEST_ASSERT_EQUAL_STRING("", cmd.display.labels[8]);
}

void test_display_utf8_truncation() {
  // 8 znaków, w tym wielobajtowe – obcięcie do 7 bez łamania sekwencji.
  ParseResult r = parse(
      "{\"type\":\"display\",\"mode\":\"grid\",\"labels\":[\"\xC5\x82\xC4\x85" "abcdef\"]}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL_STRING("\xC5\x82\xC4\x85" "abcde", cmd.display.labels[0]);
}

void test_display_bar_and_text() {
  ParseResult r = parse("{\"type\":\"display\",\"mode\":\"bar\",\"title\":\"Vol\",\"value\":150,\"ms\":1500}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL(DisplayMode::Bar, cmd.display.mode);
  TEST_ASSERT_EQUAL_UINT8(100, cmd.display.value);
  TEST_ASSERT_EQUAL_UINT32(1500, cmd.display.ms);

  r = parse("{\"type\":\"display\",\"mode\":\"text\",\"line1\":\"A\",\"line2\":\"B\"}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL(DisplayMode::Text, cmd.display.mode);
  TEST_ASSERT_EQUAL_STRING("A", cmd.display.line1);
  TEST_ASSERT_EQUAL_UINT32(0, cmd.display.ms);
}

void test_display_errors() {
  ParseResult r = parse("{\"type\":\"display\",\"id\":3,\"mode\":\"weird\"}");
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, r.status);
  TEST_ASSERT_TRUE(cmd.hasId);
  TEST_ASSERT_EQUAL_INT32(3, cmd.id);
  r = parse("{\"type\":\"display\",\"mode\":\"grid\",\"labels\":\"x\"}");
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, r.status);
  r = parse("{\"type\":\"display\",\"mode\":\"text\",\"line1\":5}");
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, r.status);
}

void test_flash() {
  ParseResult r = parse("{\"type\":\"flash\",\"key\":3,\"text\":\"Spotify\",\"ms\":1200}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL_UINT8(3, cmd.flash.key);
  TEST_ASSERT_EQUAL_STRING("Spotify", cmd.flash.text);
  TEST_ASSERT_EQUAL_UINT32(1200, cmd.flash.ms);
  r = parse("{\"type\":\"flash\",\"key\":11,\"text\":\"x\"}");
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, r.status);
}

void test_settings_partial() {
  ParseResult r = parse("{\"type\":\"settings\",\"id\":1,\"brightness\":200,\"flip\":true}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  Settings s;
  cmd.settings.applyTo(s);
  TEST_ASSERT_EQUAL_UINT8(200, s.brightness);
  TEST_ASSERT_TRUE(s.flip);
  TEST_ASSERT_EQUAL_UINT8(4, s.encPulses);  // bez zmian
  TEST_ASSERT_EQUAL_UINT8(8, s.debounceMs);
}

void test_settings_validation() {
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"settings\",\"brightness\":300}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"settings\",\"enc_pulses\":0}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"settings\",\"flip\":1}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"settings\",\"debounce_ms\":\"8\"}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Ok, parse("{\"type\":\"settings\",\"screensaver_s\":0}").status);
}

void test_fallback_single() {
  ParseResult r = parse("{\"type\":\"set_fallback\",\"key\":1,\"mods\":[\"ctrl\",\"shift\"],\"code\":\"c\"}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL_UINT8(1, cmd.fallback.count);
  TEST_ASSERT_EQUAL_UINT8(0, cmd.fallback.slots[0]);
  TEST_ASSERT_EQUAL_UINT8(kModLCtrl | kModLShift, cmd.fallback.bindings[0].mods);
  TEST_ASSERT_EQUAL_UINT8(0x06, cmd.fallback.bindings[0].code);
}

void test_fallback_list_and_replace() {
  ParseResult r = parse(
      "{\"type\":\"set_fallback\",\"replace\":true,\"bindings\":["
      "{\"key\":\"enc_cw\",\"media\":\"vol_up\"},{\"key\":\"enc_ccw\",\"media\":\"vol_down\"},"
      "{\"key\":10,\"media\":\"mute\"},{\"key\":2,\"mods\":[\"win\"],\"code\":\"f13\"}]}");
  TEST_ASSERT_EQUAL(ParseStatus::Ok, r.status);
  TEST_ASSERT_EQUAL_UINT8(4, cmd.fallback.count);

  FallbackBinding slots[kFallbackSlots];
  slots[4].code = 0x10;
  cmd.fallback.applyTo(slots);
  TEST_ASSERT_TRUE(slots[4].empty());  // replace wyczyścił
  TEST_ASSERT_EQUAL_UINT16(kConsumerVolUp, slots[kSlotEncCw].media);
  TEST_ASSERT_EQUAL_UINT16(kConsumerVolDown, slots[kSlotEncCcw].media);
  TEST_ASSERT_EQUAL_UINT16(kConsumerMute, slots[9].media);
  TEST_ASSERT_EQUAL_UINT8(kModLGui, slots[1].mods);
  TEST_ASSERT_EQUAL_UINT8(0x68, slots[1].code);
}

void test_fallback_errors() {
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"set_fallback\",\"key\":11,\"code\":\"a\"}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"set_fallback\",\"key\":1,\"code\":\"nope\"}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"set_fallback\",\"key\":1,\"mods\":[\"hyper\"]}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"set_fallback\",\"key\":1,\"code\":\"a\",\"media\":\"mute\"}").status);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"set_fallback\"}").status);
  // Pusty wpis czyści przypisanie.
  TEST_ASSERT_EQUAL(ParseStatus::Ok, parse("{\"type\":\"set_fallback\",\"key\":5}").status);
  TEST_ASSERT_TRUE(cmd.fallback.bindings[0].empty());
}

void test_reboot_and_flags() {
  TEST_ASSERT_EQUAL(ParseStatus::Ok, parse("{\"type\":\"reboot\",\"bootloader\":true}").status);
  TEST_ASSERT_EQUAL(CommandType::Reboot, cmd.type);
  TEST_ASSERT_TRUE(cmd.flag);
  TEST_ASSERT_EQUAL(ParseStatus::Ok, parse("{\"type\":\"reboot\"}").status);
  TEST_ASSERT_FALSE(cmd.flag);
  TEST_ASSERT_EQUAL(ParseStatus::Ok, parse("{\"type\":\"test_mode\"}").status);
  TEST_ASSERT_TRUE(cmd.flag);
  TEST_ASSERT_EQUAL(ParseStatus::Invalid, parse("{\"type\":\"debug\",\"enable\":\"yes\"}").status);
}

void test_build_messages() {
  char buf[256];
  size_t n = buildKey(buf, sizeof(buf), 3, true, 1234);
  TEST_ASSERT_EQUAL_STRING("{\"type\":\"key\",\"key\":3,\"action\":\"down\",\"t\":1234}", buf);
  TEST_ASSERT_EQUAL(strlen(buf), n);
  buildEnc(buf, sizeof(buf), -2, 99);
  TEST_ASSERT_EQUAL_STRING("{\"type\":\"enc\",\"steps\":-2,\"t\":99}", buf);
  buildAck(buf, sizeof(buf), 7);
  TEST_ASSERT_EQUAL_STRING("{\"type\":\"ack\",\"id\":7}", buf);
  buildError(buf, sizeof(buf), false, 0, "invalid json");
  TEST_ASSERT_EQUAL_STRING("{\"type\":\"error\",\"msg\":\"invalid json\"}", buf);
  buildHello(buf, sizeof(buf), "kb2040", "1.0.0", false);
  TEST_ASSERT_EQUAL_STRING(
      "{\"type\":\"hello\",\"device\":\"tap32\",\"fw\":\"1.0.0\",\"board\":\"kb2040\","
      "\"keys\":10,\"encoder\":true,\"hid\":true,\"online\":false}",
      buf);
  // Diagnostyka I²C: OLED znaleziony / brak odpowiedzi.
  I2cDiag diag;
  diag.oledAddr = 0x3D;
  diag.count = 1;
  diag.devices[0] = 0x3D;
  buildHello(buf, sizeof(buf), "kb2040", "1.0.0", true, &diag);
  TEST_ASSERT_NOT_NULL(strstr(buf, "\"oled\":61,\"i2c\":[61]"));
  diag = I2cDiag();
  buildHello(buf, sizeof(buf), "kb2040", "1.0.0", true, &diag);
  TEST_ASSERT_NOT_NULL(strstr(buf, "\"oled\":null,\"i2c\":[]"));
  diag.sdaLevel = 0;
  diag.sclLevel = 1;
  diag.swapped = true;
  buildHello(buf, sizeof(buf), "kb2040", "1.0.0", true, &diag);
  TEST_ASSERT_NOT_NULL(strstr(buf, "\"lines\":{\"sda\":0,\"scl\":1},\"swapped\":true"));
  // Za mały bufor → 0.
  TEST_ASSERT_EQUAL(0, buildHello(buf, 10, "kb2040", "1.0.0", false));
}

void test_hid_codes() {
  TEST_ASSERT_EQUAL_UINT8(0x04, hidKeyFromName("a"));
  TEST_ASSERT_EQUAL_UINT8(0x1D, hidKeyFromName("Z"));
  TEST_ASSERT_EQUAL_UINT8(0x27, hidKeyFromName("0"));
  TEST_ASSERT_EQUAL_UINT8(0x3A, hidKeyFromName("f1"));
  TEST_ASSERT_EQUAL_UINT8(0x45, hidKeyFromName("f12"));
  TEST_ASSERT_EQUAL_UINT8(0x68, hidKeyFromName("f13"));
  TEST_ASSERT_EQUAL_UINT8(0x73, hidKeyFromName("F24"));
  TEST_ASSERT_EQUAL_UINT8(0, hidKeyFromName("f25"));
  TEST_ASSERT_EQUAL_UINT8(0x28, hidKeyFromName("enter"));
  TEST_ASSERT_EQUAL_UINT8(0x62, hidKeyFromName("kp_0"));
  TEST_ASSERT_EQUAL_UINT8(0x38, hidKeyFromName("/"));
  TEST_ASSERT_EQUAL_UINT8(kModRAlt, hidModFromName("ralt"));
  TEST_ASSERT_EQUAL_UINT16(kConsumerPlayPause, consumerFromName("play_pause"));
  TEST_ASSERT_EQUAL_UINT16(0, consumerFromName("louder"));
}

void test_config_roundtrip() {
  DeviceConfig cfg;
  cfg.setDefaults();
  cfg.settings.brightness = 42;
  cfg.settings.flip = true;
  cfg.fallback[0].mods = kModLCtrl;
  cfg.fallback[0].code = 0x06;
  cfg.display.mode = DisplayMode::Grid;
  copyUtf8(cfg.display.title, sizeof(cfg.display.title), "Stream", kTitleChars);
  copyUtf8(cfg.display.labels[4], kLabelBuf, "Mic", kLabelChars);

  char buf[1536];
  const size_t n = encodeConfig(cfg, buf, sizeof(buf));
  TEST_ASSERT_TRUE(n > 0);

  DeviceConfig back;
  TEST_ASSERT_TRUE(decodeConfig(buf, n, back));
  TEST_ASSERT_EQUAL_UINT8(42, back.settings.brightness);
  TEST_ASSERT_TRUE(back.settings.flip);
  TEST_ASSERT_EQUAL_UINT8(kModLCtrl, back.fallback[0].mods);
  TEST_ASSERT_EQUAL_UINT16(kConsumerMute, back.fallback[9].media);
  TEST_ASSERT_EQUAL(DisplayMode::Grid, back.display.mode);
  TEST_ASSERT_EQUAL_STRING("Stream", back.display.title);
  TEST_ASSERT_EQUAL_STRING("Mic", back.display.labels[4]);
}

void test_config_corrupted_uses_defaults() {
  DeviceConfig cfg;
  TEST_ASSERT_FALSE(decodeConfig("{garbage", 8, cfg));
  TEST_ASSERT_EQUAL_UINT8(128, cfg.settings.brightness);
  TEST_ASSERT_EQUAL_UINT16(kConsumerVolUp, cfg.fallback[kSlotEncCw].media);
}

void test_debouncer() {
  Debouncer d;
  d.reset(false, 0);
  TEST_ASSERT_FALSE(d.update(true, 1, 8));   // początek zmiany
  TEST_ASSERT_FALSE(d.update(false, 2, 8));  // drganie – reset czasu
  TEST_ASSERT_FALSE(d.update(true, 3, 8));
  TEST_ASSERT_FALSE(d.update(true, 10, 8));  // 7 ms stabilnie – za mało
  TEST_ASSERT_TRUE(d.update(true, 11, 8));   // 8 ms → wciśnięty
  TEST_ASSERT_TRUE(d.pressed());
  TEST_ASSERT_FALSE(d.update(true, 50, 8));  // bez zmian
  TEST_ASSERT_FALSE(d.update(false, 51, 8));
  TEST_ASSERT_TRUE(d.update(false, 59, 8));
  TEST_ASSERT_FALSE(d.pressed());
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_invalid_json);
  RUN_TEST(test_unknown_type_is_ignored);
  RUN_TEST(test_ping_with_id_and_unknown_fields);
  RUN_TEST(test_hello_without_id);
  RUN_TEST(test_display_grid);
  RUN_TEST(test_display_utf8_truncation);
  RUN_TEST(test_display_bar_and_text);
  RUN_TEST(test_display_errors);
  RUN_TEST(test_flash);
  RUN_TEST(test_settings_partial);
  RUN_TEST(test_settings_validation);
  RUN_TEST(test_fallback_single);
  RUN_TEST(test_fallback_list_and_replace);
  RUN_TEST(test_fallback_errors);
  RUN_TEST(test_reboot_and_flags);
  RUN_TEST(test_build_messages);
  RUN_TEST(test_hid_codes);
  RUN_TEST(test_config_roundtrip);
  RUN_TEST(test_config_corrupted_uses_defaults);
  RUN_TEST(test_debouncer);
  return UNITY_END();
}
