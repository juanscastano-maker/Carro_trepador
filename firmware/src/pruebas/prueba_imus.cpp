// Prueba de las dos MPU6050 (GY-521) con sus pines INT.
//
// Qué verifica:
//   1. Que las dos IMU respondan en el bus I2C (0x68 delantera, 0x69 trasera).
//   2. Que el pin INT de cada una llegue al ESP32: la frecuencia de interrupciones debe ser
//      ~100 Hz. Si sale 0 Hz, el cable INT está suelto o en el pin equivocado.
//   3. Que las lecturas tengan sentido: con el robot plano y quieto, az ≈ +9.8 m/s².
//   4. El ángulo entre módulos (diferencia de cabeceo), que estima la articulación central.
//
// Uso: pio run -e prueba_imus -t upload && pio device monitor
// Comandos: "c" recalibra el giroscopio (robot quieto), "p" pausa/reanuda la impresión.
#include <Arduino.h>
#include <Wire.h>

#include "Consola.h"
#include "Mpu6050.h"
#include "pines.h"

namespace {
Mpu6050 imu_del, imu_tras;
bool ok_del = false, ok_tras = false;
LecturaImu ult_del{}, ult_tras{};
bool imprimir = true;
Consola consola;

constexpr float GRADOS = 57.2957795f;

// Cabeceo (pitch) a partir del acelerómetro: positivo con la nariz hacia arriba.
float cabeceo(const LecturaImu& l) { return atan2f(l.ax, sqrtf(l.ay * l.ay + l.az * l.az)) * GRADOS; }
// Alabeo (roll): positivo con el lado izquierdo hacia arriba.
float alabeo(const LecturaImu& l) { return atan2f(l.ay, l.az) * GRADOS; }

void escanearBus() {
  Serial.print("Dispositivos I2C encontrados:");
  int n = 0;
  for (uint8_t d = 1; d < 127; d++) {
    Wire.beginTransmission(d);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", d);
      n++;
    }
  }
  Serial.println(n ? "" : " ninguno (revisar SDA/SCL, alimentación y GND)");
}

bool iniciar(Mpu6050& imu, uint8_t dir, int pin_int, const char* nombre) {
  if (!imu.begin(Wire, dir, pin_int)) {
    Serial.printf("[ERROR] IMU %s (0x%02X) no responde. Revisar cableado y el pin AD0.\n", nombre, dir);
    return false;
  }
  Serial.printf("IMU %s lista (0x%02X, WHO_AM_I=0x%02X%s), INT en GPIO %d\n", nombre, dir,
                imu.quienSoy(), imu.quienSoy() == 0x68 ? "" : " <- clon, funciona igual", pin_int);
  return true;
}

void calibrar() {
  Serial.println("Calibrando giroscopios: NO mover el robot por 2 segundos...");
  if (ok_del) imu_del.calibrarGiroscopio();
  if (ok_tras) imu_tras.calibrarGiroscopio();
  Serial.println("Calibración lista.");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=== Prueba de IMUs (MPU6050 x2) ===");

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_FRECUENCIA);
  Wire.setTimeOut(20);
  escanearBus();

  ok_del = iniciar(imu_del, DIR_IMU_DELANTERA, PIN_INT_IMU_DELANTERA, "delantera");
  ok_tras = iniciar(imu_tras, DIR_IMU_TRASERA, PIN_INT_IMU_TRASERA, "trasera");
  if (ok_del || ok_tras) calibrar();
  Serial.println("Comandos: c = recalibrar giroscopio, p = pausar/reanudar impresión\n");
}

void loop() {
  const uint32_t ahora = millis();

  // Leer solo cuando el pin INT avisa que hay dato nuevo
  if (ok_del && imu_del.datoNuevo()) imu_del.leer(ult_del);
  if (ok_tras && imu_tras.datoNuevo()) imu_tras.leer(ult_tras);

  if (consola.leer()) {
    if (consola.linea()[0] == 'c') calibrar();
    if (consola.linea()[0] == 'p') imprimir = !imprimir;
  }

  // Reporte cada 500 ms
  static uint32_t ultimo_reporte = 0;
  static uint32_t int_del_antes = 0, int_tras_antes = 0;
  if (ahora - ultimo_reporte >= 500) {
    const float dt = (ahora - ultimo_reporte) / 1000.0f;
    const float hz_del = (imu_del.interrupciones() - int_del_antes) / dt;
    const float hz_tras = (imu_tras.interrupciones() - int_tras_antes) / dt;
    int_del_antes = imu_del.interrupciones();
    int_tras_antes = imu_tras.interrupciones();
    ultimo_reporte = ahora;
    if (!imprimir) return;

    if (ok_del) {
      Serial.printf("DEL  INT %5.1f Hz | a=(%6.2f %6.2f %6.2f) m/s2 | g=(%6.2f %6.2f %6.2f) rad/s | "
                    "cabeceo %6.1f° alabeo %6.1f° | %4.1f°C%s\n",
                    hz_del, ult_del.ax, ult_del.ay, ult_del.az, ult_del.gx, ult_del.gy, ult_del.gz,
                    cabeceo(ult_del), alabeo(ult_del), ult_del.temperatura,
                    hz_del < 50 ? "  <- INT sin pulsos: revisar cable INT" : "");
    }
    if (ok_tras) {
      Serial.printf("TRAS INT %5.1f Hz | a=(%6.2f %6.2f %6.2f) m/s2 | g=(%6.2f %6.2f %6.2f) rad/s | "
                    "cabeceo %6.1f° alabeo %6.1f° | %4.1f°C%s\n",
                    hz_tras, ult_tras.ax, ult_tras.ay, ult_tras.az, ult_tras.gx, ult_tras.gy,
                    ult_tras.gz, cabeceo(ult_tras), alabeo(ult_tras), ult_tras.temperatura,
                    hz_tras < 50 ? "  <- INT sin pulsos: revisar cable INT" : "");
    }
    if (ok_del && ok_tras) {
      // Con la articulación pasiva solo en cabeceo, la diferencia aproxima su ángulo
      Serial.printf("Ángulo entre módulos (articulación central) ≈ %6.1f°\n\n",
                    cabeceo(ult_del) - cabeceo(ult_tras));
    }
  }
}
