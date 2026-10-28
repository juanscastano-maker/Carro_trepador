// Lectura de comandos por el monitor serie, línea por línea, sin bloquear el loop.
#pragma once

#include <Arduino.h>

class Consola {
 public:
  // Devuelve true cuando se completó una línea (terminada en Enter). La línea queda en linea().
  bool leer() {
    while (Serial.available()) {
      const char c = static_cast<char>(Serial.read());
      if (c == '\r') continue;
      if (c == '\n') {
        buffer_[largo_] = '\0';
        largo_ = 0;
        return true;
      }
      if (largo_ < sizeof(buffer_) - 1) buffer_[largo_++] = c;
    }
    return false;
  }

  const char* linea() const { return buffer_; }

 private:
  char buffer_[64] = {0};
  size_t largo_ = 0;
};
