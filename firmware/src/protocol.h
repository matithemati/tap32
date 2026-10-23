// Łącze z aplikacją: odczyt linii JSON z USB CDC i nieblokujące wysyłanie wiadomości.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "protocol_codec.h"

namespace tap32 {

class Link {
 public:
  using LineHandler = void (*)(const char* line, size_t len);

  void begin();
  // Czyta dostępne bajty; dla każdej pełnej linii woła handler.
  void poll(LineHandler handler);

  void sendHello(bool online);
  void sendKey(uint8_t key, bool down, uint32_t t);
  void sendEnc(int32_t steps, uint32_t t);
  void sendAck(int32_t id);
  void sendError(bool hasId, int32_t id, const char* msg);
  void sendLog(const char* level, const char* msg);
  void sendTest(bool active);

  bool debug = false;

 private:
  void sendRaw(size_t len);

  char rx_[kMaxLineLength];
  size_t rxLen_ = 0;
  bool overflow_ = false;
  char tx_[256];
};

}  // namespace tap32
