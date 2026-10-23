// Ekran OLED SSD1306 128×32 (U8g2). Rysuje tylko przy zmianie stanu.
#pragma once

#include <stdint.h>

#include "device_config.h"
#include "protocol_codec.h"

namespace tap32 {

struct TestSnapshot {
  bool keys[kTotalKeys] = {false};
  int32_t encPulses = 0;
  int32_t encSteps = 0;
};

class Display {
 public:
  bool begin(const Settings& settings);
  void applySettings(const Settings& settings);

  void setOnline(bool online);
  // Tryb bazowy z pamięci (profile / grid).
  void restore(const DisplayState& state);
  // Komenda display: profile/grid oraz text/bar bez ms ustawiają tryb bazowy,
  // text/bar z ms – nakładkę chwilową.
  void apply(const DisplayCommand& cmd, uint32_t nowMs);
  void flash(uint8_t key, const char* text, uint32_t ms, uint32_t nowMs);

  void setTestMode(bool active);
  void setTestSnapshot(const TestSnapshot& snapshot);

  // Aktywność użytkownika – wybudza z wygaszacza.
  void activity(uint32_t nowMs);
  void update(uint32_t nowMs);

  // Wynik skanu I²C z begin() (adres OLED albo 0, gdy ekran nie odpowiada).
  const I2cDiag& diag() const { return diag_; }

 private:
  void draw(uint32_t nowMs);
  void drawSplash();
  void drawOffline();
  void drawBase();
  void drawCommand(const DisplayCommand& cmd);
  void drawFlash();
  void drawTest();
  void drawStatusMarker(int x, int y, bool inverted);

  bool ready_ = false;
  bool dirty_ = true;
  bool online_ = false;
  bool testMode_ = false;
  bool sleeping_ = false;
  uint16_t screensaverS_ = 0;
  uint32_t lastActivity_ = 0;
  uint32_t splashUntil_ = 0;
  uint32_t lastDraw_ = 0;

  DisplayCommand base_;
  DisplayCommand overlay_;
  uint32_t overlayUntil_ = 0;
  bool overlayActive_ = false;

  FlashCommand flash_;
  uint32_t flashUntil_ = 0;
  bool flashActive_ = false;

  TestSnapshot test_;
  I2cDiag diag_;
};

}  // namespace tap32
