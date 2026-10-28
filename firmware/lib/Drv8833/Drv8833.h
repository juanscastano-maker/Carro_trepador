// Control de los 4 motores N20 con un DRV8833 (dos puentes H), con rampa de aceleración.
//
// Canal A = lado izquierdo, canal B = lado derecho (dos motores en paralelo por canal).
// La velocidad va de -1 (atrás) a 1 (adelante). Los cambios pasan por una rampa: el motor
// acelera y frena de forma gradual, y un cambio de sentido siempre frena hasta cero primero.
//
// PWM en "decaimiento lento" (slow decay, tabla 2 de la hoja de datos del DRV8833): da una
// velocidad más proporcional al ciclo útil que el decaimiento rápido. Con velocidad cero el
// puente queda en freno (ambas entradas en alto), lo que ayuda a que el robot no ruede.
#pragma once

#include <Arduino.h>

#include "Rampa.h"

class Drv8833 {
 public:
  struct Canal {
    int pin_in1;
    int pin_in2;
    uint8_t ledc_in1;
    uint8_t ledc_in2;
    bool invertir;  // true si el motor quedó cableado al revés
  };

  // aceleracion/frenado: fracción de velocidad máxima por segundo (0.5 = de 0 a 100 % en 2 s)
  Drv8833(float aceleracion, float frenado)
      : rampa_a_(aceleracion, frenado), rampa_b_(aceleracion, frenado) {}

  void begin(int pin_sleep, const Canal& a, const Canal& b, uint32_t frecuencia_hz = 20000);

  // Habilita o deshabilita el chip (nSLEEP). Dormido, los motores quedan libres.
  void habilitar(bool si);
  bool habilitado() const { return habilitado_; }

  // Velocidad objetivo de cada lado, de -1 a 1. Se alcanza con la rampa.
  void fijarObjetivo(float izquierda, float derecha);
  // Límite de seguridad para pruebas (0 a 1).
  void fijarMaximo(float maximo) { maximo_ = constrain(maximo, 0.0f, 1.0f); }
  void fijarRampa(float aceleracion, float frenado);

  // Llamar en cada vuelta del loop: avanza la rampa y actualiza el PWM.
  void actualizar();

  // Parada inmediata sin rampa: frena ambos lados (emergencia).
  void frenarYa();

  float velocidadIzquierda() const { return rampa_a_.valor(); }
  float velocidadDerecha() const { return rampa_b_.valor(); }

 private:
  void aplicar(const Canal& c, float velocidad);

  Canal a_{}, b_{};
  int pin_sleep_ = -1;
  uint32_t max_duty_ = 1023;
  float maximo_ = 1.0f;
  bool habilitado_ = false;
  Rampa rampa_a_, rampa_b_;
};
