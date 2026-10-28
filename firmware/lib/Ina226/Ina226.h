// Driver mínimo para el INA226 (voltaje, corriente y potencia) por registros.
//
// El INA226 mide la caída de voltaje en una resistencia shunt externa. El rango de corriente
// depende de esa resistencia: corriente máxima = 81.92 mV / R_shunt.
//   Módulo típico con shunt R100 (0.1 Ω)  ->  máximo ~0.82 A  (NO alcanza para las turbinas)
//   Shunt externo de 0.001 Ω (R001, 2 W+) ->  máximo ~82 A, resolución 2.5 mA (el del proyecto)
// Ver docs/electronica/Conexiones_Carro_trepador_v3.docx.
#pragma once

#include <Arduino.h>
#include <Wire.h>

struct LecturaPotencia {
  float voltaje;      // voltaje de la batería [V]: VBUS (lado de la carga) + caída en el shunt
  float corriente;    // [A], positiva hacia la carga
  float potencia;     // [W]
  float voltaje_shunt_mv;
};

class Ina226 {
 public:
  // r_shunt en ohmios; corriente_max en amperios (define la resolución).
  // Devuelve false si el chip no responde o no es un INA226.
  bool begin(TwoWire& bus, uint8_t direccion, float r_shunt, float corriente_max);

  bool leer(LecturaPotencia& lectura);

  // ALERT se activa (pasa a bajo) si el voltaje del bus cae por debajo de este valor.
  bool alertaBajoVoltaje(float voltios);
  // ALERT se activa si la corriente supera este valor.
  bool alertaSobrecorriente(float amperios);

  // true si la última alerta la generó el INA226 (lee y limpia el indicador del chip).
  bool alertaActiva();

  float resolucionCorriente() const { return lsb_corriente_; }

 private:
  bool escribir(uint8_t registro, uint16_t valor);
  bool leer16(uint8_t registro, uint16_t& valor);

  TwoWire* bus_ = nullptr;
  uint8_t dir_ = 0x40;
  float r_shunt_ = 0.1f;
  float lsb_corriente_ = 0.0f;  // [A por bit]
};
