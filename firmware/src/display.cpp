#include "display.h"

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <string.h>

#include "boards/board.h"
#include "config.h"
#include "time_util.h"

namespace tap32 {

namespace {

// Sprzętowe I²C (Wire) albo programowe – wybór stałą board::kOledSoftI2c (np. gdy na PCB
// SDA/SCL trafiły na piny, których sprzętowy kontroler I²C nie obsługuje w tej roli).
U8G2_SSD1306_128X32_UNIVISION_F_HW_I2C hwOled(U8G2_R0, U8X8_PIN_NONE);
U8G2_SSD1306_128X32_UNIVISION_F_SW_I2C swOled(U8G2_R0, board::kScl, board::kSda, U8X8_PIN_NONE);
U8G2& u8g2 = board::kOledSoftI2c ? static_cast<U8G2&>(swOled) : static_cast<U8G2&>(hwOled);

// Czcionki: 5x7 mieści 7 znaków w komórce 42 px (siatka 3×3 + pasek tytułu = 32 px).
const uint8_t* const kFontSmall = u8g2_font_5x7_tf;
const uint8_t* const kFontText = u8g2_font_6x10_tf;
const uint8_t* const kFontPolish = u8g2_font_6x12_te;  // zawiera ą ę ł ń ś ź ż
const uint8_t* const kFontMedium = u8g2_font_helvB10_tf;
const uint8_t* const kFontLarge = u8g2_font_helvB14_tf;
const uint8_t* const kFontHuge = u8g2_font_helvB18_tf;

constexpr int kWidth = 128;
constexpr int kHeight = 32;
constexpr uint32_t kSplashMs = 1500;
constexpr uint32_t kTestRedrawMs = 33;

// Rysuje napis wyśrodkowany w poziomie, wybierając największą czcionkę, która się mieści.
void drawCenteredFit(const char* text, int baseline, const uint8_t* const* fonts, int count) {
  for (int i = 0; i < count; ++i) {
    u8g2.setFont(fonts[i]);
    const int w = u8g2.getUTF8Width(text);
    if (w <= kWidth - 2 || i == count - 1) {
      u8g2.drawUTF8((kWidth - w) / 2, baseline, text);
      return;
    }
  }
}

void drawCentered(const char* text, int cx, int baseline) {
  const int w = u8g2.getUTF8Width(text);
  u8g2.drawUTF8(cx - w / 2, baseline, text);
}

// --- programowe sprawdzenie adresu I²C (linie open-drain emulowane przez INPUT_PULLUP)
constexpr uint32_t kSoftHalfUs = 5;  // ok. 100 kHz

// Piny programowego I²C (mogą zostać zamienione, jeśli ekran odpowiada odwrotnie).
uint8_t gSda = board::kSda;
uint8_t gScl = board::kScl;

void lineLow(uint8_t pin) {
  digitalWrite(pin, LOW);
  pinMode(pin, OUTPUT);
}

void lineRelease(uint8_t pin) { pinMode(pin, INPUT_PULLUP); }

bool softProbe(uint8_t addr) {
  lineRelease(gSda);
  lineRelease(gScl);
  delayMicroseconds(kSoftHalfUs);
  if (digitalRead(gSda) == LOW || digitalRead(gScl) == LOW) return false;  // zwarcie
  // START
  lineLow(gSda);
  delayMicroseconds(kSoftHalfUs);
  lineLow(gScl);
  delayMicroseconds(kSoftHalfUs);
  // adres + bit zapisu
  const uint8_t byte = static_cast<uint8_t>(addr << 1);
  for (int8_t bit = 7; bit >= 0; --bit) {
    if (byte & (1 << bit)) {
      lineRelease(gSda);
    } else {
      lineLow(gSda);
    }
    delayMicroseconds(kSoftHalfUs);
    lineRelease(gScl);
    delayMicroseconds(kSoftHalfUs);
    lineLow(gScl);
  }
  // ACK od urządzenia
  lineRelease(gSda);
  delayMicroseconds(kSoftHalfUs);
  lineRelease(gScl);
  delayMicroseconds(kSoftHalfUs);
  const bool ack = digitalRead(gSda) == LOW;
  lineLow(gScl);
  delayMicroseconds(kSoftHalfUs);
  // STOP
  lineLow(gSda);
  delayMicroseconds(kSoftHalfUs);
  lineRelease(gScl);
  delayMicroseconds(kSoftHalfUs);
  lineRelease(gSda);
  delayMicroseconds(kSoftHalfUs);
  return ack;
}

bool probe(uint8_t addr) {
  if (board::kOledSoftI2c) return softProbe(addr);
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

void scanBus(I2cDiag& diag) {
  diag.count = 0;
  for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
    if (probe(addr) && diag.count < sizeof(diag.devices)) diag.devices[diag.count++] = addr;
  }
}

}  // namespace

bool Display::begin(const Settings& settings) {
  // Skan magistrali: diagnostyka i automatyczny wybór adresu (0x3C / 0x3D).
  diag_ = I2cDiag();
  if (board::kOledSoftI2c) {
    // Stan linii bez wewnętrznego pull-upu: wysoki tylko, gdy moduł jest zasilony i ma rezystory.
    pinMode(board::kSda, INPUT);
    pinMode(board::kScl, INPUT);
    delay(2);
    diag_.sdaLevel = digitalRead(board::kSda) == HIGH ? 1 : 0;
    diag_.sclLevel = digitalRead(board::kScl) == HIGH ? 1 : 0;
  }
  scanBus(diag_);
  if (board::kOledSoftI2c && diag_.count == 0) {
    // Nic nie odpowiada – może SDA i SCL są zamienione na płytce lub module.
    gSda = board::kScl;
    gScl = board::kSda;
    scanBus(diag_);
    if (diag_.count > 0) {
      diag_.swapped = true;
    } else {
      gSda = board::kSda;
      gScl = board::kScl;
    }
  }
  if (board::kOledSoftI2c) {
    u8x8_SetPin(u8g2.getU8x8(), U8X8_PIN_I2C_DATA, gSda);
    u8x8_SetPin(u8g2.getU8x8(), U8X8_PIN_I2C_CLOCK, gScl);
  }
  uint8_t addr = settings.oledAddr;
  if (!probe(addr)) {
    if (probe(0x3C)) {
      addr = 0x3C;
    } else if (probe(0x3D)) {
      addr = 0x3D;
    } else {
      addr = 0;
    }
  }
  diag_.oledAddr = addr;

  u8g2.setI2CAddress(static_cast<uint8_t>((addr != 0 ? addr : settings.oledAddr) << 1));
  ready_ = u8g2.begin();
  u8g2.enableUTF8Print();
  applySettings(settings);
  splashUntil_ = millis() + kSplashMs;
  lastActivity_ = millis();
  dirty_ = true;
  return ready_;
}

void Display::applySettings(const Settings& settings) {
  screensaverS_ = settings.screensaverS;
  if (!ready_) return;
  u8g2.setContrast(settings.brightness);
  u8g2.setDisplayRotation(settings.flip ? U8G2_R2 : U8G2_R0);
  dirty_ = true;
}

void Display::setOnline(bool online) {
  if (online_ == online) return;
  online_ = online;
  dirty_ = true;
}

void Display::restore(const DisplayState& state) {
  base_ = DisplayCommand();
  base_.mode = state.mode;
  memcpy(base_.title, state.title, sizeof(base_.title));
  memcpy(base_.labels, state.labels, sizeof(base_.labels));
  dirty_ = true;
}

void Display::apply(const DisplayCommand& cmd, uint32_t nowMs) {
  const bool transient = (cmd.mode == DisplayMode::Text || cmd.mode == DisplayMode::Bar) && cmd.ms > 0;
  if (transient) {
    overlay_ = cmd;
    overlayUntil_ = nowMs + cmd.ms;
    overlayActive_ = true;
  } else {
    base_ = cmd;
    overlayActive_ = false;
  }
  dirty_ = true;
}

void Display::flash(uint8_t key, const char* text, uint32_t ms, uint32_t nowMs) {
  flash_.key = key;
  copyUtf8(flash_.text, sizeof(flash_.text), text, kTitleChars);
  flash_.ms = ms;
  flashUntil_ = nowMs + ms;
  flashActive_ = true;
  activity(nowMs);
  dirty_ = true;
}

void Display::setTestMode(bool active) {
  testMode_ = active;
  dirty_ = true;
}

void Display::setTestSnapshot(const TestSnapshot& snapshot) {
  if (memcmp(&snapshot, &test_, sizeof(test_)) != 0) {
    test_ = snapshot;
    if (testMode_) dirty_ = true;
  }
}

void Display::activity(uint32_t nowMs) {
  lastActivity_ = nowMs;
  if (sleeping_) {
    sleeping_ = false;
    if (ready_) u8g2.setPowerSave(0);
    dirty_ = true;
  }
}

void Display::update(uint32_t nowMs) {
  if (!ready_) return;

  if (splashUntil_ != 0 && static_cast<int32_t>(nowMs - splashUntil_) >= 0) {
    splashUntil_ = 0;
    dirty_ = true;
  }
  if (overlayActive_ && static_cast<int32_t>(nowMs - overlayUntil_) >= 0) {
    overlayActive_ = false;
    dirty_ = true;
  }
  if (flashActive_ && static_cast<int32_t>(nowMs - flashUntil_) >= 0) {
    flashActive_ = false;
    dirty_ = true;
  }

  // Wygaszacz (nie w trybie testu).
  if (!sleeping_ && !testMode_ && screensaverS_ > 0 &&
      elapsed(nowMs, lastActivity_, static_cast<uint32_t>(screensaverS_) * 1000UL)) {
    sleeping_ = true;
    u8g2.setPowerSave(1);
    return;
  }
  if (sleeping_ || !dirty_) return;
  if (testMode_ && nowMs - lastDraw_ < kTestRedrawMs) return;

  dirty_ = false;
  lastDraw_ = nowMs;
  draw(nowMs);
}

void Display::draw(uint32_t nowMs) {
  (void)nowMs;
  u8g2.clearBuffer();
  u8g2.setDrawColor(1);
  u8g2.setFontMode(1);
  if (splashUntil_ != 0) {
    drawSplash();
  } else if (testMode_) {
    drawTest();
  } else if (flashActive_) {
    drawFlash();
  } else if (!online_) {
    drawOffline();
  } else if (overlayActive_) {
    drawCommand(overlay_);
  } else {
    drawBase();
  }
  u8g2.sendBuffer();
}

void Display::drawStatusMarker(int x, int y, bool inverted) {
  u8g2.setDrawColor(inverted ? 0 : 1);
  if (online_) {
    u8g2.drawDisc(x, y, 2);
  } else {
    u8g2.drawCircle(x, y, 2);
  }
  u8g2.setDrawColor(1);
}

void Display::drawSplash() {
  u8g2.setFont(kFontHuge);
  drawCentered("Tap32", kWidth / 2, 20);
  u8g2.setFont(kFontSmall);
  char line[40];
  snprintf(line, sizeof(line), "fw %s  %s", TAP32_FW_VERSION, board::kBoardName);
  drawCentered(line, kWidth / 2, 31);
}

void Display::drawOffline() {
  u8g2.setFont(kFontMedium);
  drawCentered("Offline", kWidth / 2, 13);
  u8g2.setFont(kFontPolish);
  drawCentered("Czekam na aplikację", kWidth / 2, 28);
  drawStatusMarker(kWidth - 4, 3, false);
}

void Display::drawBase() {
  if (base_.mode == DisplayMode::None) {
    u8g2.setFont(kFontLarge);
    drawCentered("Tap32", kWidth / 2, 22);
    drawStatusMarker(kWidth - 4, 3, false);
    return;
  }
  drawCommand(base_);
}

void Display::drawCommand(const DisplayCommand& cmd) {
  switch (cmd.mode) {
    case DisplayMode::Profile: {
      static const uint8_t* const fonts[] = {kFontLarge, kFontMedium, kFontText, kFontSmall};
      drawCenteredFit(cmd.title, 23, fonts, 4);
      drawStatusMarker(kWidth - 4, 3, false);
      break;
    }
    case DisplayMode::Grid: {
      // Pasek tytułu (odwrócony) + 3 wiersze etykiet po 8 px.
      u8g2.drawBox(0, 0, kWidth, 8);
      u8g2.setFont(kFontSmall);
      u8g2.setDrawColor(0);
      u8g2.drawUTF8(2, 7, cmd.title);
      u8g2.setDrawColor(1);
      drawStatusMarker(kWidth - 4, 3, true);
      for (int r = 0; r < 3; ++r) {
        for (int c = 0; c < 3; ++c) {
          const int cx = c * 43 + 21;
          drawCentered(cmd.labels[r * 3 + c], cx, 15 + r * 8);
        }
      }
      u8g2.drawVLine(42, 9, 23);
      u8g2.drawVLine(85, 9, 23);
      break;
    }
    case DisplayMode::Text: {
      static const uint8_t* const fonts1[] = {kFontMedium, kFontText};
      static const uint8_t* const fonts2[] = {kFontText, kFontSmall};
      if (cmd.line2[0] == '\0') {
        static const uint8_t* const big[] = {kFontLarge, kFontMedium, kFontText};
        drawCenteredFit(cmd.line1, 23, big, 3);
      } else {
        drawCenteredFit(cmd.line1, 13, fonts1, 2);
        drawCenteredFit(cmd.line2, 29, fonts2, 2);
      }
      break;
    }
    case DisplayMode::Bar: {
      u8g2.setFont(kFontText);
      u8g2.drawUTF8(0, 10, cmd.title);
      char pct[8];
      snprintf(pct, sizeof(pct), "%u%%", static_cast<unsigned>(cmd.value));
      u8g2.drawUTF8(kWidth - u8g2.getUTF8Width(pct), 10, pct);
      u8g2.drawFrame(0, 16, kWidth, 14);
      const int fill = (kWidth - 4) * cmd.value / 100;
      if (fill > 0) u8g2.drawBox(2, 18, fill, 10);
      break;
    }
    case DisplayMode::None:
      break;
  }
}

void Display::drawFlash() {
  static const uint8_t* const fonts[] = {kFontHuge, kFontLarge, kFontMedium, kFontText};
  drawCenteredFit(flash_.text, 24, fonts, 4);
  if (flash_.key != 0) {
    char tag[6];
    snprintf(tag, sizeof(tag), "K%u", static_cast<unsigned>(flash_.key));
    u8g2.setFont(kFontSmall);
    u8g2.drawUTF8(0, 7, tag);
  }
}

void Display::drawTest() {
  // Lewa część: siatka 3×3 (kwadraty 9 px), obok przycisk enkodera; prawa: liczniki.
  for (int r = 0; r < 3; ++r) {
    for (int c = 0; c < 3; ++c) {
      const int x = 1 + c * 11;
      const int y = 1 + r * 10;
      if (test_.keys[r * 3 + c]) {
        u8g2.drawBox(x, y, 9, 9);
      } else {
        u8g2.drawFrame(x, y, 9, 9);
      }
    }
  }
  if (test_.keys[kEncoderKey - 1]) {
    u8g2.drawDisc(43, 15, 6);
  } else {
    u8g2.drawCircle(43, 15, 6);
  }
  u8g2.setFont(kFontSmall);
  char line[24];
  u8g2.drawUTF8(56, 7, "TEST");
  snprintf(line, sizeof(line), "imp %ld", static_cast<long>(test_.encPulses));
  u8g2.drawUTF8(56, 18, line);
  snprintf(line, sizeof(line), "zab %ld", static_cast<long>(test_.encSteps));
  u8g2.drawUTF8(56, 28, line);
}

}  // namespace tap32
