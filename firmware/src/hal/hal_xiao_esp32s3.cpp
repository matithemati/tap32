// HAL: Seeed XIAO ESP32-S3 (Arduino-ESP32 3.x, USB OTG/TinyUSB, Preferences/NVS, LED GPIO21).
#if defined(TAP32_BOARD_XIAO_ESP32S3)

#include <Arduino.h>
#include <Preferences.h>
#include <USB.h>
#include <USBHIDConsumerControl.h>
#include <USBHIDKeyboard.h>
#include <Wire.h>
#include <esp32-hal-tinyusb.h>
#include <string.h>

#include "../boards/board.h"
#include "hal.h"

namespace tap32 {
namespace hal {

namespace {

USBHIDKeyboard keyboard;
USBHIDConsumerControl consumer;
Preferences prefs;

const char* const kNamespace = "tap32";
const char* const kConfigKey = "cfg";

LedState ledState = LedState::Offline;
uint32_t pulseUntil = 0;
bool pulseActive = false;
bool ledOn = false;

void writeLed(bool on) {
  if (on == ledOn) return;
  ledOn = on;
  digitalWrite(board::kLedPin, (on != board::kLedActiveLow) ? HIGH : LOW);
}

}  // namespace

// --- board ---

void usbBegin() {
  USB.productName("Tap32");
  USB.manufacturerName("Tap32");
  keyboard.begin();
  consumer.begin();
  USB.begin();
}

void i2cBegin() {
  Wire.begin(board::kSda, board::kScl);
  Wire.setClock(400000);
}

void reboot(bool bootloader) {
  delay(50);  // czas na wysłanie ack
  if (bootloader) {
    usb_persist_restart(RESTART_BOOTLOADER);
  }
  ESP.restart();
  while (true) {
  }
}

// --- storage ---

bool storageBegin() { return prefs.begin(kNamespace, false); }

size_t storageLoad(char* buf, size_t cap) {
  const size_t len = prefs.getBytesLength(kConfigKey);
  if (len == 0 || len >= cap) return 0;
  const size_t n = prefs.getBytes(kConfigKey, buf, len);
  buf[n] = '\0';
  return n;
}

bool storageSave(const char* data, size_t len) {
  // NVS zapisuje wpis atomowo (stara wartość pozostaje do zatwierdzenia nowej).
  return prefs.putBytes(kConfigKey, data, len) == len;
}

// --- usb_hid ---

bool hidReady() { return static_cast<bool>(USB); }

void hidKeyboardReport(uint8_t mods, const uint8_t keys[6]) {
  KeyReport report;
  report.modifiers = mods;
  report.reserved = 0;
  memcpy(report.keys, keys, sizeof(report.keys));
  keyboard.sendReport(&report);
}

void hidConsumerReport(uint16_t usage) {
  if (usage != 0) {
    consumer.press(usage);
  } else {
    consumer.release();
  }
}

// --- status_led ---

void statusLedBegin() {
  pinMode(board::kLedPin, OUTPUT);
  ledOn = true;
  writeLed(false);
}

void statusLedSet(LedState state) { ledState = state; }

void statusLedPulse() {
  pulseUntil = millis() + 30;
  pulseActive = true;
}

void statusLedUpdate(uint32_t nowMs) {
  if (pulseActive && static_cast<int32_t>(nowMs - pulseUntil) >= 0) pulseActive = false;

  bool on = false;
  switch (ledState) {
    case LedState::Online:
      on = true;  // świeci
      break;
    case LedState::Offline:
      on = (nowMs / 500) % 2 == 0;  // miga 1 Hz
      break;
    case LedState::Test:
      on = (nowMs / 100) % 2 == 0;  // miga szybko
      break;
  }
  if (pulseActive) on = !on;  // krótkie mrugnięcie przy zdarzeniu
  writeLed(on);
}

}  // namespace hal
}  // namespace tap32

#endif  // TAP32_BOARD_XIAO_ESP32S3
