// Driver mínimo para la MPU6050 (módulo GY-521) por registros, con interrupción de dato listo.
//
// Configuración: muestreo a 100 Hz, filtro pasa bajos de 44 Hz, acelerómetro ±4 g,
// giroscopio ±500 °/s. El pin INT da un pulso de 50 µs cada vez que hay una muestra nueva;
// la interrupción del ESP32 solo marca una bandera y la lectura se hace en el loop.
#pragma once

#include <Arduino.h>
#include <Wire.h>

struct LecturaImu {
  float ax, ay, az;  // aceleración [m/s²], ejes del sensor
  float gx, gy, gz;  // velocidad angular [rad/s], ya sin el sesgo calibrado
  float temperatura; // [°C]
};

class Mpu6050 {
 public:
  // Devuelve false si el sensor no responde o no es una MPU6050.
  bool begin(TwoWire& bus, uint8_t direccion, int pin_int);

  // true si llegó una interrupción desde la última lectura.
  bool datoNuevo() const { return pendiente_; }

  // Lee aceleración, giro y temperatura (14 bytes de una vez). Limpia la bandera.
  bool leer(LecturaImu& lectura);

  // Promedia el giroscopio con el sensor quieto para quitar su sesgo.
  bool calibrarGiroscopio(uint16_t muestras = 200);

  uint32_t interrupciones() const { return interrupciones_; }
  uint8_t direccion() const { return dir_; }
  uint8_t quienSoy() const { return quien_soy_; }  // 0x68 = MPU6050 original

 private:
  static void IRAM_ATTR alInterrumpir(void* arg);
  bool escribir(uint8_t registro, uint8_t valor);
  bool leerBytes(uint8_t registro, uint8_t* datos, size_t n);

  TwoWire* bus_ = nullptr;
  uint8_t dir_ = 0x68;
  uint8_t quien_soy_ = 0;
  float sesgo_g_[3] = {0, 0, 0};
  volatile bool pendiente_ = false;
  volatile uint32_t interrupciones_ = 0;
};
