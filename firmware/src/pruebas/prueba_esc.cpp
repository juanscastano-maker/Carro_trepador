// Prueba de los 2 ESC Hobbywing Skywalker V2 y las turbinas, con aceleración gradual.
//
// PELIGRO: las hélices a 4600 KV en 4S cortan. Primera prueba SIN HÉLICES, con el robot sujeto.
//
// Rampa por defecto: el acelerador sube 20 %/s (de 0 a 100 % en 5 s) y baja 40 %/s. Además
// conviene programar el ESC en "Start-up Mode: Soft o Very Soft" (ver documento de conexiones).
// Tope por defecto: 30 %. El motor XING2 1404 4600KV es para 2S-3S; en 4S puede pasar su
// corriente máxima a todo acelerador, así que subir el tope de a poco y vigilando la temperatura.
//
// El cable amarillo del ESC (cuarto cable) NO va conectado al ESP32: es para la caja de
// programación o para invertir el giro, y una turbina invertida empujaría el robot fuera de
// la pared.
//
// Uso: pio run -e prueba_esc -t upload && pio device monitor
// Comandos:
//   d P / t P / a P   acelerador en % de la turbina delantera, trasera o ambas (ej.: a 15)
//   0                 bajar ambas con rampa hasta 0 %
//   x                 corte inmediato de ambas
//   max P             tope del acelerador en % (por defecto 30)
//   rampa A F         subida y bajada en %/s (ej.: rampa 20 40)
//   calibrar          calibrar el rango de acelerador de los ESC (sin hélices)
#include <Arduino.h>

#include "Consola.h"
#include "EscPwm.h"
#include "pines.h"

namespace {
float subida = 0.20f;  // fracción por segundo
float bajada = 0.40f;
float tope = 0.30f;
// Si no llega ningún comando en este tiempo, las turbinas bajan solas a 0 % (seguridad en pruebas)
constexpr uint32_t SIN_COMANDOS_MS = 60000;

EscPwm esc_del(subida, bajada), esc_tras(subida, bajada);
Consola consola;
uint32_t ultimo_comando = 0;

enum class Modo { Normal, CalibrandoMax };
Modo modo = Modo::Normal;

void ayuda() {
  Serial.println("Comandos: d P, t P, a P, 0, x, max P, rampa A F, calibrar");
}

void iniciarCalibracion() {
  Serial.println("\n=== CALIBRACIÓN DEL RANGO DE ACELERADOR ===");
  Serial.println("1. QUITAR LAS HÉLICES y DESCONECTAR la batería de los ESC.");
  Serial.println("2. Ahora el ESP32 envía 100 % (2000 µs) a ambos ESC.");
  Serial.println("3. Conectar la batería: suena '123' y luego dos pitidos cortos.");
  Serial.println("4. Dentro de 5 s después de los dos pitidos, escribir 'listo' y Enter.");
  Serial.println("   (Para cancelar sin conectar la batería, escribir 'cancelar'.)");
  esc_del.pulsoDirecto(2000);
  esc_tras.pulsoDirecto(2000);
  modo = Modo::CalibrandoMax;
}

void procesar(const char* l) {
  float p1 = 0, p2 = 0;
  if (modo == Modo::CalibrandoMax) {
    if (!strcmp(l, "listo")) {
      esc_del.pulsoDirecto(1000);
      esc_tras.pulsoDirecto(1000);
      Serial.println("Enviando 0 % (1000 µs). Deben sonar los pitidos de celdas (4) y uno largo:");
      Serial.println("calibración guardada. Rango 1000-2000 µs.");
    } else if (!strcmp(l, "cancelar")) {
      esc_del.cortarYa();
      esc_tras.cortarYa();
      Serial.println("Calibración cancelada.");
    } else {
      Serial.println("Escribir 'listo' o 'cancelar'.");
      return;
    }
    modo = Modo::Normal;
    return;
  }

  if (!strcmp(l, "0")) {
    esc_del.fijarObjetivo(0);
    esc_tras.fijarObjetivo(0);
    Serial.println("Bajando ambas a 0 % con rampa.");
  } else if (!strcmp(l, "x")) {
    esc_del.cortarYa();
    esc_tras.cortarYa();
    Serial.println("CORTE INMEDIATO.");
  } else if (!strcmp(l, "calibrar")) {
    iniciarCalibracion();
  } else if (sscanf(l, "max %f", &p1) == 1) {
    tope = constrain(p1, 0, 100) / 100;
    esc_del.fijarMaximo(tope);
    esc_tras.fijarMaximo(tope);
    Serial.printf("Tope del acelerador: %.0f %%\n", tope * 100);
  } else if (sscanf(l, "rampa %f %f", &p1, &p2) == 2 && p1 > 0 && p2 > 0) {
    subida = p1 / 100;
    bajada = p2 / 100;
    esc_del.fijarRampa(subida, bajada);
    esc_tras.fijarRampa(subida, bajada);
    Serial.printf("Rampa: sube %.0f %%/s, baja %.0f %%/s\n", p1, p2);
  } else if (sscanf(l, "d %f", &p1) == 1) {
    esc_del.fijarObjetivo(p1 / 100);
    Serial.printf("Turbina delantera -> %.0f %% (tope %.0f %%)\n", min(p1, tope * 100), tope * 100);
  } else if (sscanf(l, "t %f", &p1) == 1) {
    esc_tras.fijarObjetivo(p1 / 100);
    Serial.printf("Turbina trasera -> %.0f %% (tope %.0f %%)\n", min(p1, tope * 100), tope * 100);
  } else if (sscanf(l, "a %f", &p1) == 1) {
    esc_del.fijarObjetivo(p1 / 100);
    esc_tras.fijarObjetivo(p1 / 100);
    Serial.printf("Ambas turbinas -> %.0f %% (tope %.0f %%)\n", min(p1, tope * 100), tope * 100);
  } else {
    ayuda();
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  // Ambos ESC reciben 0 % desde el arranque para poder armarse
  esc_del.begin(PIN_ESC_DELANTERO, LEDC_ESC_DELANTERO);
  esc_tras.begin(PIN_ESC_TRASERO, LEDC_ESC_TRASERO);
  esc_del.fijarMaximo(tope);
  esc_tras.fijarMaximo(tope);
  enableLoopWDT();  // si el loop se cuelga 5 s, el ESP32 se reinicia y los ESC cortan por falta de señal

  delay(1500);
  Serial.println("\n=== Prueba de ESC y turbinas (Skywalker V2 x2) ===");
  Serial.println("PRIMERA PRUEBA SIN HÉLICES. Enviando 0 % a ambos ESC.");
  Serial.println("Conectar la batería: '123', 4 pitidos (4S) y un pitido largo = ESC armado.");
  Serial.printf("Tope %.0f %%, rampa: sube %.0f %%/s, baja %.0f %%/s\n", tope * 100, subida * 100,
                bajada * 100);
  ayuda();
  ultimo_comando = millis();
}

void loop() {
  if (modo == Modo::Normal) {
    esc_del.actualizar();
    esc_tras.actualizar();
  }

  if (consola.leer()) {
    ultimo_comando = millis();
    procesar(consola.linea());
  }

  const bool girando = esc_del.acelerador() > 0 || esc_tras.acelerador() > 0;
  if (modo == Modo::Normal && girando && millis() - ultimo_comando > SIN_COMANDOS_MS) {
    esc_del.fijarObjetivo(0);
    esc_tras.fijarObjetivo(0);
    ultimo_comando = millis();
    Serial.println("Sin comandos por 60 s: bajando las turbinas a 0 % por seguridad.");
  }

  static uint32_t ultimo = 0;
  if (girando && millis() - ultimo >= 250) {
    ultimo = millis();
    Serial.printf("Delantera %5.1f %% (%4u µs) | Trasera %5.1f %% (%4u µs)\n",
                  esc_del.acelerador() * 100, esc_del.pulsoActual(), esc_tras.acelerador() * 100,
                  esc_tras.pulsoActual());
  }
}
