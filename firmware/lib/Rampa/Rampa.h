// Limitador de pendiente: lleva un valor hacia su objetivo a una velocidad máxima.
// Se usa para que motores y turbinas arranquen y frenen de forma gradual, evitando
// picos de corriente y golpes mecánicos.
//
// Trabaja con valores con signo (por ejemplo -1..1 para un motor que va en ambos sentidos).
// "Acelerar" es alejarse de cero y "frenar" es acercarse a cero, cada uno con su propia
// velocidad. Un cambio de sentido siempre pasa por cero: primero frena y luego acelera.
#pragma once

#include <Arduino.h>

class Rampa {
 public:
  // aceleracion y frenado en unidades por segundo (por ejemplo 0.5 = de 0 a 1 en 2 s)
  Rampa(float aceleracion, float frenado) : acel_(aceleracion), fren_(frenado) {}

  void fijarObjetivo(float objetivo) { objetivo_ = objetivo; }
  float objetivo() const { return objetivo_; }
  float valor() const { return valor_; }
  bool enObjetivo() const { return valor_ == objetivo_; }

  void fijarVelocidades(float aceleracion, float frenado) {
    acel_ = aceleracion;
    fren_ = frenado;
  }

  // Salta al valor sin rampa (por ejemplo, en una parada de emergencia).
  void forzar(float v) {
    valor_ = v;
    objetivo_ = v;
    ultimo_us_ = micros();
  }

  // Llamar seguido (en cada vuelta de loop). Devuelve el valor actualizado.
  float actualizar() {
    const uint32_t ahora = micros();
    if (ultimo_us_ == 0) {
      ultimo_us_ = ahora;
      return valor_;
    }
    float dt = (ahora - ultimo_us_) * 1e-6f;
    ultimo_us_ = ahora;
    if (dt > 0.1f) dt = 0.1f;  // si el loop se trabó, no dar un salto grande

    const float diferencia = objetivo_ - valor_;
    if (diferencia == 0.0f) return valor_;

    // Acelera si se aleja de cero (o parte de cero); frena si se acerca a cero.
    const bool acelerando = (valor_ == 0.0f) || ((diferencia > 0.0f) == (valor_ > 0.0f));
    const float paso = (acelerando ? acel_ : fren_) * dt;

    if (fabsf(diferencia) <= paso) {
      valor_ = objetivo_;
    } else {
      float nuevo = valor_ + (diferencia > 0.0f ? paso : -paso);
      // Al frenar, detenerse en cero antes de cambiar de sentido
      if (!acelerando && ((nuevo > 0.0f) != (valor_ > 0.0f))) nuevo = 0.0f;
      valor_ = nuevo;
    }
    return valor_;
  }

 private:
  float acel_;
  float fren_;
  float objetivo_ = 0.0f;
  float valor_ = 0.0f;
  uint32_t ultimo_us_ = 0;
};
