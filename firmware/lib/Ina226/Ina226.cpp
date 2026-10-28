#include "Ina226.h"

namespace {
// Registros (hoja de datos INA226, TI SBOS547)
constexpr uint8_t REG_CONFIG = 0x00;
constexpr uint8_t REG_SHUNT = 0x01;        // 2.5 µV por bit
constexpr uint8_t REG_BUS = 0x02;          // 1.25 mV por bit
constexpr uint8_t REG_POTENCIA = 0x03;     // 25 × LSB de corriente
constexpr uint8_t REG_CORRIENTE = 0x04;
constexpr uint8_t REG_CALIBRACION = 0x05;
constexpr uint8_t REG_MASK_ENABLE = 0x06;
constexpr uint8_t REG_LIMITE_ALERTA = 0x07;
constexpr uint8_t REG_FABRICANTE = 0xFE;   // 0x5449 ("TI")
constexpr uint8_t REG_DIE_ID = 0xFF;       // 0x2260 en el INA226

constexpr uint16_t MASK_SOL = 1 << 15;     // sobre-voltaje en el shunt (sobrecorriente)
constexpr uint16_t MASK_BUL = 1 << 12;     // bajo voltaje en el bus
constexpr uint16_t MASK_AFF = 1 << 4;      // indicador: la alerta fue del INA226
constexpr uint16_t MASK_LEN = 1 << 0;      // alerta enclavada hasta leer Mask/Enable
}  // namespace

bool Ina226::begin(TwoWire& bus, uint8_t direccion, float r_shunt, float corriente_max) {
  bus_ = &bus;
  dir_ = direccion;
  r_shunt_ = r_shunt;

  uint16_t fabricante = 0, die = 0;
  if (!leer16(REG_FABRICANTE, fabricante) || !leer16(REG_DIE_ID, die)) return false;
  if (fabricante != 0x5449 || (die & 0xFFF0) != 0x2260) return false;

  escribir(REG_CONFIG, 0x8000);  // reinicio
  delay(2);
  // Promedio de 16 muestras, 1.1 ms por conversión de bus y de shunt, modo continuo:
  // una lectura nueva cada ~35 ms. 0x4000 son bits fijos del registro.
  const uint16_t config = 0x4000 | (0b010 << 9) | (0b100 << 6) | (0b100 << 3) | 0b111;
  if (!escribir(REG_CONFIG, config)) return false;

  // Calibración (ecuaciones 1 y 2 de la hoja de datos)
  lsb_corriente_ = corriente_max / 32768.0f;
  uint32_t cal = static_cast<uint32_t>(0.00512f / (lsb_corriente_ * r_shunt_));
  if (cal > 0xFFFF) {  // shunt muy chico para esa resolución: usar la mínima posible
    cal = 0xFFFF;
    lsb_corriente_ = 0.00512f / (cal * r_shunt_);
  }
  return escribir(REG_CALIBRACION, static_cast<uint16_t>(cal));
}

bool Ina226::leer(LecturaPotencia& l) {
  uint16_t bus = 0, shunt = 0, corriente = 0, potencia = 0;
  if (!leer16(REG_BUS, bus) || !leer16(REG_SHUNT, shunt) || !leer16(REG_CORRIENTE, corriente) ||
      !leer16(REG_POTENCIA, potencia)) {
    return false;
  }
  l.voltaje_shunt_mv = static_cast<int16_t>(shunt) * 0.0025f;
  // VBUS se mide del lado de la carga (IN−): sumando la caída del shunt se obtiene la batería
  l.voltaje = bus * 0.00125f + l.voltaje_shunt_mv / 1000.0f;
  l.corriente = static_cast<int16_t>(corriente) * lsb_corriente_;
  l.potencia = potencia * 25.0f * lsb_corriente_;
  return true;
}

bool Ina226::alertaBajoVoltaje(float voltios) {
  const uint16_t limite = static_cast<uint16_t>(voltios / 0.00125f);
  return escribir(REG_LIMITE_ALERTA, limite) && escribir(REG_MASK_ENABLE, MASK_BUL | MASK_LEN);
}

bool Ina226::alertaSobrecorriente(float amperios) {
  // La comparación se hace contra el voltaje del shunt (2.5 µV por bit)
  const float limite_v = amperios * r_shunt_;
  const uint16_t limite = static_cast<uint16_t>(limite_v / 0.0000025f);
  return escribir(REG_LIMITE_ALERTA, limite) && escribir(REG_MASK_ENABLE, MASK_SOL | MASK_LEN);
}

bool Ina226::alertaActiva() {
  uint16_t mask = 0;
  if (!leer16(REG_MASK_ENABLE, mask)) return false;  // leer este registro libera la alerta
  return (mask & MASK_AFF) != 0;
}

bool Ina226::escribir(uint8_t registro, uint16_t valor) {
  bus_->beginTransmission(dir_);
  bus_->write(registro);
  bus_->write(static_cast<uint8_t>(valor >> 8));
  bus_->write(static_cast<uint8_t>(valor & 0xFF));
  return bus_->endTransmission() == 0;
}

bool Ina226::leer16(uint8_t registro, uint16_t& valor) {
  bus_->beginTransmission(dir_);
  bus_->write(registro);
  if (bus_->endTransmission(false) != 0) return false;
  if (bus_->requestFrom(dir_, static_cast<uint8_t>(2)) != 2) return false;
  const uint8_t alto = bus_->read();  // en dos líneas: el orden de lectura importa
  const uint8_t bajo = bus_->read();
  valor = (static_cast<uint16_t>(alto) << 8) | bajo;
  return true;
}
