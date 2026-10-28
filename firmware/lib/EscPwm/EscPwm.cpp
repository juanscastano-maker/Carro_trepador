#include "EscPwm.h"

namespace {
constexpr uint32_t FRECUENCIA_HZ = 50;   // periodo de 20 ms, estándar de servos y ESC
constexpr uint8_t BITS_PWM = 14;         // 16384 pasos en 20 ms: ~1.22 µs por paso
constexpr uint32_t PERIODO_US = 1000000 / FRECUENCIA_HZ;
}  // namespace

void EscPwm::begin(int pin, uint8_t canal_ledc, uint16_t pulso_min_us, uint16_t pulso_max_us) {
  pin_ = pin;
  canal_ = canal_ledc;
  min_us_ = pulso_min_us;
  max_us_ = pulso_max_us;
  ledcSetup(canal_, FRECUENCIA_HZ, BITS_PWM);
  ledcAttachPin(pin_, canal_);
  rampa_.forzar(0.0f);
  escribirPulso(min_us_);
}

void EscPwm::fijarObjetivo(float acelerador) {
  rampa_.fijarObjetivo(constrain(acelerador, 0.0f, maximo_));
}

void EscPwm::actualizar() {
  const float a = rampa_.actualizar();
  escribirPulso(min_us_ + static_cast<uint16_t>(a * (max_us_ - min_us_) + 0.5f));
}

void EscPwm::cortarYa() {
  rampa_.forzar(0.0f);
  escribirPulso(min_us_);
}

void EscPwm::pulsoDirecto(uint16_t microsegundos) {
  rampa_.forzar(0.0f);
  escribirPulso(microsegundos);
}

void EscPwm::escribirPulso(uint16_t us) {
  if (us == pulso_us_) return;
  pulso_us_ = us;
  const uint32_t duty = (static_cast<uint32_t>(us) << BITS_PWM) / PERIODO_US;
  ledcWrite(canal_, duty);
}
