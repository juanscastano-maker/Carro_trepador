// Prueba del INA226: voltaje de la batería, corriente, potencia y pin ALERT.
//
// ANTES DE USAR: ajustar R_SHUNT y CORRIENTE_MAX al shunt de tu módulo.
//   Módulo de fábrica (shunt R100 = 0.1 Ω): mide hasta ~0.8 A. Sirve para probar el sensor,
//   pero NO para medir el robot completo (las turbinas consumen decenas de amperios).
//   Con el shunt externo de 1 mΩ (R001, 2 W o más, conexión Kelvin): poner R_SHUNT = 0.001 y
//   CORRIENTE_MAX = 80 (81.92 mV / 0.001 Ω), con 2.5 mA de resolución.
//
// El pin ALERT del INA226 comparte el GPIO 3 con nFAULT del DRV8833. Si el pin baja, esta
// prueba le pregunta al INA226 si fue él; si no, la alerta vino del DRV8833.
//
// Uso: pio run -e prueba_potencia -t upload && pio device monitor
// Comandos:
//   bv V   alerta por bajo voltaje de batería en voltios (por defecto 14.0 V = 3.5 V por celda en 4S)
//   sc A   alerta por sobrecorriente en amperios (reemplaza la de bajo voltaje: solo hay una)
#include <Arduino.h>
#include <Wire.h>

#include "Consola.h"
#include "Ina226.h"
#include "pines.h"

namespace {
// ---- Ajustar según el shunt instalado ----
constexpr float R_SHUNT = 0.1f;        // ohmios: 0.1 con la R100 de fábrica, 0.001 con el shunt externo
constexpr float CORRIENTE_MAX = 0.8f;  // amperios: 0.8 con la R100, 80 con el shunt de 1 mΩ
constexpr int CELDAS = 4;              // batería LiPo 4S
constexpr float ALERTA_BAJO_VOLTAJE = 14.0f;

Ina226 ina;
bool ok = false;
Consola consola;
volatile bool alerta = false;

void IRAM_ATTR alBajarAlerta() { alerta = true; }
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=== Prueba del INA226 (voltaje y corriente) ===");

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_FRECUENCIA);
  Wire.setTimeOut(20);

  ok = ina.begin(Wire, DIR_INA226, R_SHUNT, CORRIENTE_MAX);
  if (!ok) {
    Serial.printf("[ERROR] INA226 no responde en 0x%02X (o no es un INA226). Revisar SDA/SCL, VCC y GND.\n",
                  DIR_INA226);
    return;
  }
  Serial.printf("INA226 listo. Shunt %.4f Ω, rango ±%.2f A, resolución %.2f mA\n", R_SHUNT, CORRIENTE_MAX,
                ina.resolucionCorriente() * 1000);

  ina.alertaBajoVoltaje(ALERTA_BAJO_VOLTAJE);
  Serial.printf("Alerta por bajo voltaje: %.2f V (%.2f V por celda)\n", ALERTA_BAJO_VOLTAJE,
                ALERTA_BAJO_VOLTAJE / CELDAS);

  pinMode(PIN_ALERTA, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ALERTA), alBajarAlerta, FALLING);
  Serial.println("Comandos: bv V (bajo voltaje), sc A (sobrecorriente)\n");
}

void loop() {
  if (!ok) {
    delay(1000);
    return;
  }

  if (consola.leer()) {
    float v = 0;
    if (sscanf(consola.linea(), "bv %f", &v) == 1 && ina.alertaBajoVoltaje(v)) {
      Serial.printf("Alerta por bajo voltaje en %.2f V\n", v);
    } else if (sscanf(consola.linea(), "sc %f", &v) == 1 && ina.alertaSobrecorriente(v)) {
      Serial.printf("Alerta por sobrecorriente en %.2f A\n", v);
    } else {
      Serial.println("Comandos: bv V, sc A");
    }
  }

  if (alerta) {
    alerta = false;
    if (ina.alertaActiva()) {
      Serial.println("[ALERTA INA226] Límite superado (bajo voltaje o sobrecorriente).");
    } else {
      Serial.println("[ALERTA] El pin bajó pero no fue el INA226: revisar nFAULT del DRV8833.");
    }
  }

  static uint32_t ultimo = 0;
  if (millis() - ultimo >= 250) {
    ultimo = millis();
    LecturaPotencia l;
    if (!ina.leer(l)) {
      Serial.println("[ERROR] Falló la lectura I2C del INA226.");
      return;
    }
    const float por_celda = l.voltaje / CELDAS;
    const char* estado = por_celda >= 3.7f ? "bien" : por_celda >= 3.5f ? "media" : "BAJA: cargar";
    Serial.printf("Batería %6.3f V (%.2f V/celda, %s) | Corriente %8.4f A | Potencia %7.3f W | "
                  "Shunt %7.3f mV%s\n",
                  l.voltaje, por_celda, estado, l.corriente, l.potencia, l.voltaje_shunt_mv,
                  fabsf(l.voltaje_shunt_mv) > 80.0f ? "  <- FUERA DE RANGO: el shunt se queda corto" : "");
  }
}
