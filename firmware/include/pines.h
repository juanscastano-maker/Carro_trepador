// Mapa de pines y recursos del Carro Trepador (Freenove ESP32-S3 WROOM CAM N16R8).
// Conexiones y motivos: docs/electronica/Conexiones_Carro_trepador_v3.docx
//
// GPIO que NO se pueden usar en esta placa:
//   4-13, 15-18     cámara OV2640
//   35, 36, 37      PSRAM octal del módulo N16R8
//   43, 44          UART0 hacia el CH340 (Serial / programación)
//   0, 45, 46       pines de arranque (strapping): pueden impedir que la placa arranque
//   19, 20          USB OTG (reservados, sin usar)
//   2               tiene el LED azul de la placa: NO sirve para I2C (el LED carga la línea);
//                   sí sirve como salida normal
// La ranura microSD usa 38, 39 y 40: aquí se usan para el DRV8833, así que NO insertar tarjeta.
#pragma once

#include <stdint.h>

// ---------- Bus I2C de sensores (Wire = I2C0) ----------
// La cámara usa su propio bus (SCCB en GPIO 4/5, I2C1), así que no hay conflicto.
constexpr int PIN_I2C_SDA = 1;
constexpr int PIN_I2C_SCL = 14;
constexpr uint32_t I2C_FRECUENCIA = 100000;  // 100 kHz: más tolerante a cables largos y ruido

constexpr uint8_t DIR_IMU_DELANTERA = 0x68;  // GY-521 con AD0 a GND
constexpr uint8_t DIR_IMU_TRASERA = 0x69;    // GY-521 con AD0 a 3.3 V
constexpr uint8_t DIR_INA226 = 0x40;         // A0 y A1 a GND (valor de fábrica)

// ---------- Interrupciones ----------
constexpr int PIN_INT_IMU_DELANTERA = 21;  // INT del MPU6050 delantero (dato listo)
constexpr int PIN_INT_IMU_TRASERA = 47;    // INT del MPU6050 trasero (dato listo)
// ALERT del INA226 y nFAULT (ULT) del DRV8833 comparten este pin: los dos son
// colector abierto y activos en bajo. Si se pone en bajo, el código pregunta al INA226
// si fue él; si no, fue una falla del DRV8833.
constexpr int PIN_ALERTA = 3;

// ---------- DRV8833 (motores N20) ----------
// Nombres del módulo: IN1/IN2 -> OUT1/OUT2 = lado izquierdo (rueda media + delantera, en paralelo)
//                     IN3/IN4 -> OUT3/OUT4 = lado derecho  (rueda media + delantera, en paralelo)
constexpr int PIN_DRV_IN1 = 38;
constexpr int PIN_DRV_IN2 = 39;
constexpr int PIN_DRV_IN3 = 40;
constexpr int PIN_DRV_IN4 = 2;  // el LED azul de la placa se ilumina cuando trabaja el lado derecho
// EEP (nSLEEP) NO se conecta: el puente J1 del módulo lo une a VCC (6 V) y deja el DRV8833
// siempre activo. Conectarlo a la ESP32 con J1 cerrado la dañaría. -1 = sin pin.
constexpr int PIN_DRV_SLEEP = -1;

// ---------- LED de estado ----------
constexpr int PIN_LED_WS2812 = 48;  // LED de colores de la placa, libre para mostrar el estado

// ---------- ESC Skywalker V2 (turbinas) ----------
// Cable blanco del ESC (señal de acelerador). El cable amarillo NO se conecta (ver documento).
constexpr int PIN_ESC_DELANTERO = 41;
constexpr int PIN_ESC_TRASERO = 42;

// ---------- Canales LEDC (PWM) ----------
// En Arduino-ESP32 2.x los canales van en pares por temporizador: (0,1)->T0, (2,3)->T1,
// (4,5)->T2, (6,7)->T3. Dos canales del mismo par comparten frecuencia.
constexpr uint8_t LEDC_CAMARA_CANAL = 0;  // XCLK de la cámara (temporizador 0; el canal 1 queda libre)
constexpr uint8_t LEDC_CAMARA_TIMER = 0;
constexpr uint8_t LEDC_DRV_IN1 = 2;       // 20 kHz (temporizador 1)
constexpr uint8_t LEDC_DRV_IN2 = 3;
constexpr uint8_t LEDC_DRV_IN3 = 4;       // 20 kHz (temporizador 2)
constexpr uint8_t LEDC_DRV_IN4 = 5;
constexpr uint8_t LEDC_ESC_DELANTERO = 6; // 50 Hz (temporizador 3)
constexpr uint8_t LEDC_ESC_TRASERO = 7;

// ---------- Cámara OV2640 (fija en la placa, mismo mapa que ESP32-S3-EYE) ----------
constexpr int CAM_PIN_PWDN = -1;
constexpr int CAM_PIN_RESET = -1;
constexpr int CAM_PIN_XCLK = 15;
constexpr int CAM_PIN_SIOD = 4;
constexpr int CAM_PIN_SIOC = 5;
constexpr int CAM_PIN_Y9 = 16;
constexpr int CAM_PIN_Y8 = 17;
constexpr int CAM_PIN_Y7 = 18;
constexpr int CAM_PIN_Y6 = 12;
constexpr int CAM_PIN_Y5 = 10;
constexpr int CAM_PIN_Y4 = 8;
constexpr int CAM_PIN_Y3 = 9;
constexpr int CAM_PIN_Y2 = 11;
constexpr int CAM_PIN_VSYNC = 6;
constexpr int CAM_PIN_HREF = 7;
constexpr int CAM_PIN_PCLK = 13;
