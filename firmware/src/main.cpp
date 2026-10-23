// Tap32 – firmware. Cienka warstwa: skan klawiszy i enkodera, ekran, kilka ustawień.
// Logika akcji, gestów i profili działa w aplikacji na PC (protokół: docs/PROTOCOL.md).
#include <Arduino.h>
#include <string.h>

#include "config.h"
#include "device_config.h"
#include "display.h"
#include "encoder.h"
#include "fallback.h"
#include "hal/hal.h"
#include "matrix.h"
#include "protocol.h"
#include "protocol_codec.h"
#include "settings.h"

using namespace tap32;

namespace {

DeviceConfig gConfig;
ConfigStore gStore;
Matrix gMatrix;
Encoder gEncoder;
Display gDisplay;
Link gLink;
Fallback gFallback(gConfig.fallback);
Command gCommand;

bool gOnline = false;
uint32_t gLastRx = 0;
bool gEverRx = false;

uint32_t gLastScanUs = 0;
int32_t gEncPending = 0;
uint32_t gLastEncSend = 0;

bool gTestMode = false;
TestSnapshot gTest;
uint32_t gComboSince = 0;  // od kiedy trzymane K1+K3 (0 = nie)
bool gComboFired = false;

void applySettings() {
  gEncoder.setPulsesPerDetent(gConfig.settings.encPulses);
  gEncoder.setReverse(gConfig.settings.encReverse);
  gDisplay.applySettings(gConfig.settings);
}

void setTestMode(bool active) {
  if (gTestMode == active) return;
  gTestMode = active;
  gTest.encSteps = 0;
  gDisplay.setTestMode(active);
  gLink.sendTest(active);
}

void setOnline(bool online) {
  if (gOnline == online) return;
  gOnline = online;
  gFallback.setEnabled(!online);
  gDisplay.setOnline(online);
  gLink.sendLog("info", online ? "online" : "offline");
}

void onUserActivity(uint32_t now) {
  gDisplay.activity(now);
  hal::statusLedPulse();
}

void onKeyChange(uint8_t key, bool down) {
  const uint32_t now = millis();
  gLink.sendKey(key, down, now);
  gFallback.onKey(key, down);
  gTest.keys[key - 1] = down;
  onUserActivity(now);
}

void handleCommand(const Command& cmd, uint32_t now) {
  switch (cmd.type) {
    case CommandType::Hello:
      setOnline(true);
      gLink.sendHello(true);
      break;
    case CommandType::GetInfo:
      gLink.sendHello(gOnline);
      break;
    case CommandType::Ping:
      break;
    case CommandType::Display: {
      const DisplayCommand& d = cmd.display;
      if (d.mode == DisplayMode::Profile || d.mode == DisplayMode::Grid) {
        gConfig.display.mode = d.mode;
        memcpy(gConfig.display.title, d.title, sizeof(gConfig.display.title));
        memcpy(gConfig.display.labels, d.labels, sizeof(gConfig.display.labels));
        gStore.markDirty(now);
      }
      gDisplay.apply(d, now);
      break;
    }
    case CommandType::Flash:
      gDisplay.flash(cmd.flash.key, cmd.flash.text, cmd.flash.ms, now);
      break;
    case CommandType::Settings:
      cmd.settings.applyTo(gConfig.settings);
      applySettings();
      gStore.markDirty(now);
      break;
    case CommandType::SetFallback:
      cmd.fallback.applyTo(gConfig.fallback);
      gStore.markDirty(now);
      break;
    case CommandType::Reboot:
      if (cmd.hasId) gLink.sendAck(cmd.id);
      Serial.flush();
      gStore.flush(gConfig);
      hal::reboot(cmd.flag);
      break;
    case CommandType::TestMode:
      setTestMode(cmd.flag);
      break;
    case CommandType::Debug:
      gLink.debug = cmd.flag;
      break;
    case CommandType::Unknown:
      break;
  }
}

void onLine(const char* line, size_t len) {
  const uint32_t now = millis();
  const ParseResult result = parseCommand(line, len, gCommand);
  switch (result.status) {
    case ParseStatus::BadJson:
      gLink.sendError(false, 0, result.error);
      return;
    case ParseStatus::Invalid:
      gLastRx = now;
      gEverRx = true;
      gLink.sendError(gCommand.hasId, gCommand.id, result.error);
      return;
    case ParseStatus::Ignored:
      gLastRx = now;
      gEverRx = true;
      return;
    case ParseStatus::Ok:
      break;
  }
  gLastRx = now;
  gEverRx = true;
  handleCommand(gCommand, now);
  if (gCommand.hasId && gCommand.type != CommandType::Reboot) gLink.sendAck(gCommand.id);
}

void updateHeartbeat(uint32_t now) {
  const bool alive = gEverRx && (now - gLastRx) < kHeartbeatTimeoutMs;
  setOnline(alive);
}

void updateEncoder(uint32_t now) {
  const int32_t steps = gEncoder.takeSteps();
  if (steps != 0) {
    gEncPending += steps;
    gTest.encSteps += steps;
    gFallback.onEncoder(steps);
    onUserActivity(now);
  }
  if (gEncPending != 0 && now - gLastEncSend >= kEncReportIntervalMs) {
    gLink.sendEnc(gEncPending, now);
    gEncPending = 0;
    gLastEncSend = now;
  }
  gTest.encPulses = gEncoder.rawPulses();
}

// K1+K3 trzymane 3 s: zaraz po starcie włącza tryb testu, w trybie testu – wyłącza.
void updateTestCombo(uint32_t now) {
  const bool combo = gMatrix.pressed(1) && gMatrix.pressed(3);
  if (!combo) {
    gComboSince = 0;
    gComboFired = false;
    return;
  }
  if (gComboSince == 0) gComboSince = now;
  const bool eligible = gTestMode || gComboSince <= kTestComboBootWindowMs;
  if (eligible && !gComboFired && now - gComboSince >= kTestComboHoldMs) {
    gComboFired = true;
    setTestMode(!gTestMode);
  }
}

}  // namespace

void setup() {
  hal::usbBegin();
  gLink.begin();
  hal::statusLedBegin();

  const bool loaded = gStore.load(gConfig);
  hal::i2cBegin();
  gDisplay.begin(gConfig.settings);
  gDisplay.restore(gConfig.display);
  gLink.diag = &gDisplay.diag();

  gMatrix.begin();
  gEncoder.begin();
  applySettings();
  gFallback.setEnabled(true);

  gLink.sendHello(false);
  gLink.sendLog("info", loaded ? "config loaded" : "default config");
}

void loop() {
  const uint32_t now = millis();

  const uint32_t nowUs = micros();
  if (nowUs - gLastScanUs >= kScanIntervalUs) {
    gLastScanUs = nowUs;
    gMatrix.scan(now, gConfig.settings.debounceMs, onKeyChange);
    updateTestCombo(now);
  }

  updateEncoder(now);
  gLink.poll(onLine);
  updateHeartbeat(now);
  gFallback.update();

  gDisplay.setTestSnapshot(gTest);
  gDisplay.update(now);

  hal::statusLedSet(gTestMode ? hal::LedState::Test
                              : (gOnline ? hal::LedState::Online : hal::LedState::Offline));
  hal::statusLedUpdate(now);

  if (gStore.update(gConfig, now)) gLink.sendLog("info", "config saved");
}
