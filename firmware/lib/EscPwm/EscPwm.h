// Control de un ESC de aeromodelismo (Hobbywing Skywalker V2) con rampa de aceleración.
//
// El ESC recibe un pulso cada 20 ms (50 Hz). El ancho del pulso es el acelerador:
// 1000 µs = 0 % y 2000 µs = 100 %, después de calibrar el ESC (sin calibrar, el Skywalker usa
// 1100-1940 µs de fábrica). Si el ESC deja de recibir pulsos por más de 0.25 s, corta el motor.
//
// Armado: al conectar la batería el ESC debe recibir 0 % (1000 µs). Pita "123", luego un
// pitido por cada celda de la batería (4 en 4S) y un pitido largo: queda listo.
#pragma once

#include <Arduino.h>

#include "Rampa.h"

class EscPwm {
 public:
  // aceleracion/frenado: fracción del acelerador por segundo (0.25 = de 0 a 100 % en 4 s)
  EscPwm(float aceleracion, float frenado) : rampa_(aceleracion, frenado) {}

  // Empieza enviando 0 % para que el ESC se arme.
  void begin(int pin, uint8_t canal_ledc, uint16_t pulso_min_us = 1000, uint16_t pulso_max_us = 2000);

  // Acelerador objetivo de 0 a 1 (se recorta al máximo configurado).
  void fijarObjetivo(float acelerador);
  // Tope de seguridad del acelerador (0 a 1).
  void fijarMaximo(float maximo) { maximo_ = constrain(maximo, 0.0f, 1.0f); }
  void fijarRampa(float aceleracion, float frenado) { rampa_.fijarVelocidades(aceleracion, frenado); }

  // Llamar en cada vuelta del loop: avanza la rampa y actualiza el pulso.
  void actualizar();

  // Corte inmediato a 0 % sin rampa.
  void cortarYa();

  // Envía un ancho de pulso fijo sin rampa ni tope. SOLO para calibrar el ESC.
  void pulsoDirecto(uint16_t microsegundos);

  float acelerador() const { return rampa_.valor(); }
  uint16_t pulsoActual() const { return pulso_us_; }

 private:
  void escribirPulso(uint16_t us);

  int pin_ = -1;
  uint8_t canal_ = 0;
  uint16_t min_us_ = 1000, max_us_ = 2000, pulso_us_ = 0;
  float maximo_ = 1.0f;
  Rampa rampa_;
};
