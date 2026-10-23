#include "protocol.h"

#include <Arduino.h>

#include "boards/board.h"
#include "config.h"

namespace tap32 {

void Link::begin() { Serial.begin(115200); }

void Link::poll(LineHandler handler) {
  int budget = 512;  // ogranicz pracę w jednym obiegu pętli
  while (budget-- > 0 && Serial.available() > 0) {
    const int c = Serial.read();
    if (c < 0) break;
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflow_) {
        overflow_ = false;
        sendError(false, 0, "line too long");
      } else if (rxLen_ > 0) {
        rx_[rxLen_] = '\0';
        handler(rx_, rxLen_);
      }
      rxLen_ = 0;
      continue;
    }
    if (overflow_) continue;
    if (rxLen_ >= sizeof(rx_) - 1) {
      overflow_ = true;
      rxLen_ = 0;
      continue;
    }
    rx_[rxLen_++] = static_cast<char>(c);
  }
}

void Link::sendRaw(size_t len) {
  if (len == 0) return;
  // Bez blokowania: gdy host nie odbiera (brak aplikacji), wiadomość jest pomijana.
  if (!Serial || Serial.availableForWrite() < static_cast<int>(len + 1)) return;
  Serial.write(reinterpret_cast<const uint8_t*>(tx_), len);
  Serial.write('\n');
}

void Link::sendHello(bool online) {
  sendRaw(buildHello(tx_, sizeof(tx_), board::kBoardId, TAP32_FW_VERSION, online, diag));
}

void Link::sendKey(uint8_t key, bool down, uint32_t t) {
  sendRaw(buildKey(tx_, sizeof(tx_), key, down, t));
}

void Link::sendEnc(int32_t steps, uint32_t t) { sendRaw(buildEnc(tx_, sizeof(tx_), steps, t)); }

void Link::sendAck(int32_t id) { sendRaw(buildAck(tx_, sizeof(tx_), id)); }

void Link::sendError(bool hasId, int32_t id, const char* msg) {
  sendRaw(buildError(tx_, sizeof(tx_), hasId, id, msg));
}

void Link::sendLog(const char* level, const char* msg) {
  if (!debug) return;
  sendRaw(buildLog(tx_, sizeof(tx_), level, msg));
}

void Link::sendTest(bool active) { sendRaw(buildTest(tx_, sizeof(tx_), active)); }

}  // namespace tap32
