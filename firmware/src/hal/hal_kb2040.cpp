// HAL: Adafruit KB2040 (RP2040, arduino-pico + Adafruit TinyUSB, LittleFS, NeoPixel).
#if defined(TAP32_BOARD_KB2040)

// Ostrzeżenia z nagłówków bibliotek zewnętrznych (brakujące inicjalizatory pól) – nie nasz kod.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#include <Adafruit_NeoPixel.h>
#include <Adafruit_TinyUSB.h>
#pragma GCC diagnostic pop
#include <Arduino.h>
#include <LittleFS.h>
#include <Wire.h>
#include <string.h>

#include "../boards/board.h"
#include "hal.h"

namespace tap32 {
namespace hal {

namespace {

enum : uint8_t { kRidKeyboard = 1, kRidConsumer = 2 };

const uint8_t kHidReportDesc[] = {
    TUD_HID_REPORT_DESC_KEYBOARD(HID_REPORT_ID(kRidKeyboard)),
    TUD_HID_REPORT_DESC_CONSUMER(HID_REPORT_ID(kRidConsumer)),
};

Adafruit_USBD_HID usbHid;
Adafruit_NeoPixel pixel(1, board::kNeoPixelPin, NEO_GRB + NEO_KHZ800);

const char* const kConfigPath = "/tap32.json";
const char* const kConfigTmpPath = "/tap32.tmp";

LedState ledState = LedState::Offline;
uint32_t pulseUntil = 0;
bool pulseActive = false;
bool ledDirty = true;

uint32_t colorFor(LedState state) {
  switch (state) {
    case LedState::Online:
      return Adafruit_NeoPixel::Color(0, 255, 0);
    case LedState::Test:
      return Adafruit_NeoPixel::Color(80, 0, 255);
    case LedState::Offline:
    default:
      return Adafruit_NeoPixel::Color(255, 90, 0);
  }
}

}  // namespace

// --- board ---

void usbBegin() {
  if (!TinyUSBDevice.isInitialized()) TinyUSBDevice.begin(0);
  TinyUSBDevice.setManufacturerDescriptor("Tap32");
  TinyUSBDevice.setProductDescriptor("Tap32");

  usbHid.setPollInterval(2);
  usbHid.setReportDescriptor(kHidReportDesc, sizeof(kHidReportDesc));
  usbHid.setStringDescriptor("Tap32 HID");
  usbHid.begin();

  // Ponowne wyliczenie, żeby host zobaczył interfejs HID i nowe nazwy.
  if (TinyUSBDevice.mounted()) {
    TinyUSBDevice.detach();
    delay(10);
    TinyUSBDevice.attach();
  }
}

void i2cBegin() {
  Wire.setSDA(board::kSda);
  Wire.setSCL(board::kScl);
  Wire.begin();
  Wire.setClock(400000);
}

void reboot(bool bootloader) {
  delay(50);  // czas na wysłanie ack
  if (bootloader) {
    rp2040.rebootToBootloader();
  } else {
    rp2040.reboot();
  }
  while (true) {
  }
}

// --- storage ---

bool storageBegin() { return LittleFS.begin(); }

size_t storageLoad(char* buf, size_t cap) {
  File f = LittleFS.open(kConfigPath, "r");
  if (!f) return 0;
  const size_t n = f.read(reinterpret_cast<uint8_t*>(buf), cap - 1);
  f.close();
  buf[n] = '\0';
  return n;
}

bool storageSave(const char* data, size_t len) {
  // Zapis atomowy: plik tymczasowy, potem zamiana nazwy.
  File f = LittleFS.open(kConfigTmpPath, "w");
  if (!f) return false;
  const size_t written = f.write(reinterpret_cast<const uint8_t*>(data), len);
  f.close();
  if (written != len) return false;
  LittleFS.remove(kConfigPath);
  return LittleFS.rename(kConfigTmpPath, kConfigPath);
}

// --- usb_hid ---

bool hidReady() { return TinyUSBDevice.mounted() && usbHid.ready(); }

void hidKeyboardReport(uint8_t mods, const uint8_t keys[6]) {
  uint8_t codes[6];
  memcpy(codes, keys, sizeof(codes));
  usbHid.keyboardReport(kRidKeyboard, mods, codes);
}

void hidConsumerReport(uint16_t usage) { usbHid.sendReport16(kRidConsumer, usage); }

// --- status_led ---

void statusLedBegin() {
  pixel.begin();
  pixel.setBrightness(board::kNeoPixelBrightness);
  pixel.clear();
  pixel.show();
}

void statusLedSet(LedState state) {
  if (state != ledState) {
    ledState = state;
    ledDirty = true;
  }
}

void statusLedPulse() {
  pulseUntil = millis() + 40;
  pulseActive = true;
  ledDirty = true;
}

void statusLedUpdate(uint32_t nowMs) {
  if (pulseActive && static_cast<int32_t>(nowMs - pulseUntil) >= 0) {
    pulseActive = false;
    ledDirty = true;
  }
  if (!ledDirty) return;
  ledDirty = false;
  pixel.setPixelColor(0, pulseActive ? Adafruit_NeoPixel::Color(255, 255, 255) : colorFor(ledState));
  pixel.show();
}

}  // namespace hal
}  // namespace tap32

#endif  // TAP32_BOARD_KB2040
