// Prueba del DRV8833 y los 4 motores N20, con arranque y frenado graduales.
//
// IMPORTANTE: hacer la primera prueba con el robot levantado (ruedas en el aire).
//
// Los motores nunca saltan de golpe a la velocidad pedida: suben con una rampa (por defecto
// de 0 a 100 % en 2 s) y bajan con otra (de 100 % a 0 en 1 s). Un cambio de sentido frena
// primero hasta cero. Así se evitan picos de corriente y golpes en los engranajes.
//
// Uso: pio run -e prueba_motores -t upload && pio device monitor
// Comandos (escribir y Enter):
//   on / off        activar o desactivar las salidas (desactivado = motores libres)
//   w s a d         adelante, atrás, girar a la izquierda, girar a la derecha (a la velocidad de prueba)
//   0               frenar con rampa hasta detenerse
//   x               freno inmediato (emergencia)
//   v I D           velocidad de cada lado en %, de -100 a 100 (ej.: v 30 -30)
//   vel P           velocidad de prueba para w/s/a/d en % (ej.: vel 40)
//   max P           tope de velocidad en % (por defecto 60)
//   rampa A F       aceleración y frenado en %/s (ej.: rampa 50 100)
//   inv I D         invertir el sentido de un lado si quedó cableado al revés (ej.: inv 1 0)
#include <Arduino.h>

#include "Consola.h"
#include "Drv8833.h"
#include "pines.h"

namespace {
float aceleracion = 0.5f;  // fracción por segundo: 0 -> 100 % en 2 s
float frenado = 1.0f;      // 100 % -> 0 en 1 s
float vel_prueba = 0.4f;
float tope = 0.6f;

Drv8833 drv(aceleracion, frenado);
Drv8833::Canal canal_izq{PIN_DRV_IN1, PIN_DRV_IN2, LEDC_DRV_IN1, LEDC_DRV_IN2, false};
Drv8833::Canal canal_der{PIN_DRV_IN3, PIN_DRV_IN4, LEDC_DRV_IN3, LEDC_DRV_IN4, false};
Consola consola;

void ayuda() {
  Serial.println("Comandos: on, off, w, s, a, d, 0 (frenar suave), x (freno inmediato),");
  Serial.println("          v I D, vel P, max P, rampa A F, inv I D");
}

void mover(float izq, float der) {
  if (!drv.habilitado()) {
    Serial.println("Las salidas están desactivadas: escribir 'on' primero.");
    return;
  }
  drv.fijarObjetivo(izq, der);
  Serial.printf("Objetivo: izquierda %.0f %%, derecha %.0f %%\n", izq * 100, der * 100);
}

void procesar(const char* l) {
  float p1 = 0, p2 = 0;
  if (!strcmp(l, "on")) {
    drv.habilitar(true);
    Serial.println("Salidas del DRV8833 activadas.");
  } else if (!strcmp(l, "off")) {
    drv.habilitar(false);
    Serial.println("Salidas desactivadas: motores libres.");
  } else if (!strcmp(l, "w")) {
    mover(vel_prueba, vel_prueba);
  } else if (!strcmp(l, "s")) {
    mover(-vel_prueba, -vel_prueba);
  } else if (!strcmp(l, "a")) {
    mover(-vel_prueba, vel_prueba);
  } else if (!strcmp(l, "d")) {
    mover(vel_prueba, -vel_prueba);
  } else if (!strcmp(l, "0")) {
    mover(0, 0);
  } else if (!strcmp(l, "x")) {
    drv.frenarYa();
    Serial.println("FRENO INMEDIATO.");
  } else if (sscanf(l, "v %f %f", &p1, &p2) == 2) {
    mover(p1 / 100, p2 / 100);
  } else if (sscanf(l, "vel %f", &p1) == 1) {
    vel_prueba = constrain(p1, 0, 100) / 100;
    Serial.printf("Velocidad de prueba: %.0f %%\n", vel_prueba * 100);
  } else if (sscanf(l, "max %f", &p1) == 1) {
    tope = constrain(p1, 0, 100) / 100;
    drv.fijarMaximo(tope);
    Serial.printf("Tope de velocidad: %.0f %%\n", tope * 100);
  } else if (sscanf(l, "rampa %f %f", &p1, &p2) == 2 && p1 > 0 && p2 > 0) {
    aceleracion = p1 / 100;
    frenado = p2 / 100;
    drv.fijarRampa(aceleracion, frenado);
    Serial.printf("Rampa: acelera %.0f %%/s, frena %.0f %%/s\n", p1, p2);
  } else if (sscanf(l, "inv %f %f", &p1, &p2) == 2) {
    drv.frenarYa();
    canal_izq.invertir = p1 != 0;
    canal_der.invertir = p2 != 0;
    const bool estaba = drv.habilitado();
    drv.begin(PIN_DRV_SLEEP, canal_izq, canal_der);
    if (estaba) drv.habilitar(true);
    Serial.printf("Invertir: izquierda %d, derecha %d\n", canal_izq.invertir, canal_der.invertir);
  } else {
    ayuda();
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=== Prueba de motores (DRV8833 + 4 N20) ===");
  Serial.println("Primera prueba con el robot LEVANTADO, ruedas en el aire.");

  pinMode(PIN_ALERTA, INPUT_PULLUP);  // nFAULT del DRV8833 (compartido con ALERT del INA226)
  drv.begin(PIN_DRV_SLEEP, canal_izq, canal_der);
  drv.fijarMaximo(tope);
  Serial.printf("Tope %.0f %%, rampa: acelera %.0f %%/s, frena %.0f %%/s\n", tope * 100,
                aceleracion * 100, frenado * 100);
  ayuda();
}

void loop() {
  drv.actualizar();

  if (consola.leer()) procesar(consola.linea());

  // Falla del DRV8833: sobrecorriente, sobretemperatura o bajo voltaje en VM
  static bool falla_antes = false;
  const bool falla = digitalRead(PIN_ALERTA) == LOW;
  if (falla && !falla_antes) {
    drv.frenarYa();
    Serial.println("[FALLA] nFAULT del DRV8833 activo: sobrecorriente, temperatura o voltaje bajo. "
                   "Motores frenados.");
  }
  falla_antes = falla;

  static uint32_t ultimo = 0;
  const bool moviendo = drv.velocidadIzquierda() != 0 || drv.velocidadDerecha() != 0;
  if (moviendo && millis() - ultimo >= 250) {
    ultimo = millis();
    Serial.printf("Velocidad actual: izquierda %5.1f %%, derecha %5.1f %%\n",
                  drv.velocidadIzquierda() * 100, drv.velocidadDerecha() * 100);
  }
}
