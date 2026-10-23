// Warstwa sprzętowa (HAL). Jedyne miejsce z kodem zależnym od płytki to implementacje
// hal_kb2040.cpp i hal_xiao_esp32s3.cpp (kompilowane warunkowo w całości).
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace tap32 {
namespace hal {

// --- board ---
// Wczesna inicjalizacja USB (nazwa produktu, HID) – przed Serial.
void usbBegin();
// Uruchomienie magistrali I²C na pinach z mapy płytki.
void i2cBegin();
// Restart; bootloader=true → tryb wgrywania (UF2 / ROM download).
[[noreturn]] void reboot(bool bootloader);

// --- storage ---
// Jeden blob tekstowy (JSON) z konfiguracją urządzenia.
bool storageBegin();
// Zwraca liczbę wczytanych bajtów (0 = brak danych). Bufor zakończony \0.
size_t storageLoad(char* buf, size_t cap);
bool storageSave(const char* data, size_t len);

// --- usb_hid ---
bool hidReady();
// Raport klawiatury: modyfikatory + do 6 kodów (0 = brak).
void hidKeyboardReport(uint8_t mods, const uint8_t keys[6]);
// Consumer control: usage != 0 → wciśnięty, 0 → zwolniony.
void hidConsumerReport(uint16_t usage);

// --- status_led ---
enum class LedState : uint8_t { Offline, Online, Test };
void statusLedBegin();
void statusLedSet(LedState state);
// Krótki sygnał zdarzenia (naciśnięcie / obrót).
void statusLedPulse();
// Wywoływane w pętli – animacje (miganie, wygaszanie błysku).
void statusLedUpdate(uint32_t nowMs);

}  // namespace hal
}  // namespace tap32
