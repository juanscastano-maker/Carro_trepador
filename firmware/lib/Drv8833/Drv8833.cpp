#include "Drv8833.h"

namespace {
constexpr uint8_t BITS_PWM = 10;  // 1024 pasos a 20 kHz
}

void Drv8833::begin(int pin_sleep, const Canal& a, const Canal& b, uint32_t frecuencia_hz) {
  a_ = a;
  b_ = b;
  pin_sleep_ = pin_sleep;
  max_duty_ = (1u << BITS_PWM) - 1;

  for (const Canal* c : {&a_, &b_}) {
    ledcSetup(c->ledc_in1, frecuencia_hz, BITS_PWM);
    ledcSetup(c->ledc_in2, frecuencia_hz, BITS_PWM);
    ledcAttachPin(c->pin_in1, c->ledc_in1);
    ledcAttachPin(c->pin_in2, c->ledc_in2);
    ledcWrite(c->ledc_in1, 0);  // motores libres al iniciar
    ledcWrite(c->ledc_in2, 0);
  }
  if (pin_sleep_ >= 0) {
    pinMode(pin_sleep_, OUTPUT);
    digitalWrite(pin_sleep_, LOW);  // empieza dormido
  }
  habilitado_ = false;
}

void Drv8833::habilitar(bool si) {
  if (!si) {
    frenarYa();
    for (const Canal* c : {&a_, &b_}) {  // dormido y con entradas en bajo: motores libres
      ledcWrite(c->ledc_in1, 0);
      ledcWrite(c->ledc_in2, 0);
    }
  }
  if (pin_sleep_ >= 0) digitalWrite(pin_sleep_, si ? HIGH : LOW);
  if (si) delay(2);  // el DRV8833 tarda ~1 ms en despertar
  habilitado_ = si;
}

void Drv8833::fijarObjetivo(float izquierda, float derecha) {
  rampa_a_.fijarObjetivo(constrain(izquierda, -maximo_, maximo_));
  rampa_b_.fijarObjetivo(constrain(derecha, -maximo_, maximo_));
}

void Drv8833::fijarRampa(float aceleracion, float frenado) {
  rampa_a_.fijarVelocidades(aceleracion, frenado);
  rampa_b_.fijarVelocidades(aceleracion, frenado);
}

void Drv8833::actualizar() {
  const float va = rampa_a_.actualizar();
  const float vb = rampa_b_.actualizar();
  if (!habilitado_) return;
  aplicar(a_, va);
  aplicar(b_, vb);
}

void Drv8833::frenarYa() {
  rampa_a_.forzar(0.0f);
  rampa_b_.forzar(0.0f);
  if (habilitado_) {
    aplicar(a_, 0.0f);
    aplicar(b_, 0.0f);
  }
}

void Drv8833::aplicar(const Canal& c, float v) {
  if (c.invertir) v = -v;
  const uint32_t lleno = max_duty_;  // en Arduino-ESP32 2.x, el valor máximo = siempre encendido
  const uint32_t duty = static_cast<uint32_t>(fabsf(v) * max_duty_ + 0.5f);

  if (duty == 0) {
    // Freno: ambas entradas en alto (el motor queda en cortocircuito y resiste el giro)
    ledcWrite(c.ledc_in1, lleno);
    ledcWrite(c.ledc_in2, lleno);
  } else if (v > 0) {
    // Adelante, decaimiento lento: IN1 = 1, IN2 = PWM invertido
    ledcWrite(c.ledc_in1, lleno);
    ledcWrite(c.ledc_in2, max_duty_ - duty);
  } else {
    // Atrás, decaimiento lento: IN1 = PWM invertido, IN2 = 1
    ledcWrite(c.ledc_in1, max_duty_ - duty);
    ledcWrite(c.ledc_in2, lleno);
  }
}
