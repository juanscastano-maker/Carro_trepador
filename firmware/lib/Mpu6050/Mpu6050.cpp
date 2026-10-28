#include "Mpu6050.h"

namespace {
// Registros (hoja de registros MPU-6000/6050, rev. 4.2)
constexpr uint8_t REG_SMPLRT_DIV = 0x19;
constexpr uint8_t REG_CONFIG = 0x1A;
constexpr uint8_t REG_GYRO_CONFIG = 0x1B;
constexpr uint8_t REG_ACCEL_CONFIG = 0x1C;
constexpr uint8_t REG_INT_PIN_CFG = 0x37;
constexpr uint8_t REG_INT_ENABLE = 0x38;
constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
constexpr uint8_t REG_PWR_MGMT_1 = 0x6B;
constexpr uint8_t REG_WHO_AM_I = 0x75;

constexpr float G = 9.80665f;
constexpr float LSB_POR_G = 8192.0f;      // ±4 g
constexpr float LSB_POR_GRADO_S = 65.5f;  // ±500 °/s
constexpr float RAD_POR_GRADO = 0.01745329252f;
}  // namespace

void IRAM_ATTR Mpu6050::alInterrumpir(void* arg) {
  auto* self = static_cast<Mpu6050*>(arg);
  self->pendiente_ = true;
  self->interrupciones_++;
}

bool Mpu6050::begin(TwoWire& bus, uint8_t direccion, int pin_int) {
  bus_ = &bus;
  dir_ = direccion;

  // WHO_AM_I vale 0x68 en una MPU6050 original. Algunos módulos traen clones (0x70, 0x72, 0x98):
  // se aceptan igual, pero quienSoy() permite avisarlo.
  if (!leerBytes(REG_WHO_AM_I, &quien_soy_, 1)) return false;

  escribir(REG_PWR_MGMT_1, 0x80);  // reinicio del sensor
  delay(100);
  if (!escribir(REG_PWR_MGMT_1, 0x01)) return false;  // despertar, reloj del giroscopio X (más estable)
  delay(10);
  escribir(REG_CONFIG, 0x03);        // filtro pasa bajos: 44 Hz acelerómetro / 42 Hz giroscopio
  escribir(REG_SMPLRT_DIV, 9);       // 1 kHz / (1 + 9) = 100 Hz
  escribir(REG_GYRO_CONFIG, 0x08);   // ±500 °/s
  escribir(REG_ACCEL_CONFIG, 0x08);  // ±4 g
  escribir(REG_INT_PIN_CFG, 0x00);   // INT activo en alto, push-pull, pulso de 50 µs
  if (!escribir(REG_INT_ENABLE, 0x01)) return false;  // interrupción de dato listo

  if (pin_int >= 0) {
    pinMode(pin_int, INPUT);
    attachInterruptArg(digitalPinToInterrupt(pin_int), alInterrumpir, this, RISING);
  }
  return true;
}

bool Mpu6050::leer(LecturaImu& l) {
  uint8_t d[14];
  pendiente_ = false;
  if (!leerBytes(REG_ACCEL_XOUT_H, d, sizeof(d))) return false;

  auto palabra = [&](int i) { return static_cast<int16_t>((d[i] << 8) | d[i + 1]); };
  l.ax = palabra(0) / LSB_POR_G * G;
  l.ay = palabra(2) / LSB_POR_G * G;
  l.az = palabra(4) / LSB_POR_G * G;
  l.temperatura = palabra(6) / 340.0f + 36.53f;
  l.gx = palabra(8) / LSB_POR_GRADO_S * RAD_POR_GRADO - sesgo_g_[0];
  l.gy = palabra(10) / LSB_POR_GRADO_S * RAD_POR_GRADO - sesgo_g_[1];
  l.gz = palabra(12) / LSB_POR_GRADO_S * RAD_POR_GRADO - sesgo_g_[2];
  return true;
}

bool Mpu6050::calibrarGiroscopio(uint16_t muestras) {
  float suma[3] = {0, 0, 0};
  sesgo_g_[0] = sesgo_g_[1] = sesgo_g_[2] = 0;
  uint16_t ok = 0;
  for (uint16_t i = 0; i < muestras; i++) {
    LecturaImu l;
    if (leer(l)) {
      suma[0] += l.gx;
      suma[1] += l.gy;
      suma[2] += l.gz;
      ok++;
    }
    delay(10);  // una muestra nueva cada 10 ms (100 Hz)
  }
  if (ok == 0) return false;
  for (int i = 0; i < 3; i++) sesgo_g_[i] = suma[i] / ok;
  return true;
}

bool Mpu6050::escribir(uint8_t registro, uint8_t valor) {
  bus_->beginTransmission(dir_);
  bus_->write(registro);
  bus_->write(valor);
  return bus_->endTransmission() == 0;
}

bool Mpu6050::leerBytes(uint8_t registro, uint8_t* datos, size_t n) {
  bus_->beginTransmission(dir_);
  bus_->write(registro);
  if (bus_->endTransmission(false) != 0) return false;
  if (bus_->requestFrom(dir_, static_cast<uint8_t>(n)) != n) return false;
  for (size_t i = 0; i < n; i++) datos[i] = bus_->read();
  return true;
}
