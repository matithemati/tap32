// Porównania czasu odpornego na przepełnienie millis() i na znaczniki „z przyszłości”
// (zapisane później niż `now` odczytany na początku obiegu pętli).
#pragma once

#include <stdint.h>

namespace tap32 {

// Czy od chwili `since` minęło co najmniej `ms`? Gdy `since` jest późniejsze niż `now`
// (różnica ujemna), wynik to false – a nie „minęło 49 dni”.
inline bool elapsed(uint32_t now, uint32_t since, uint32_t ms) {
  return static_cast<int32_t>(now - since) >= static_cast<int32_t>(ms);
}

}  // namespace tap32
