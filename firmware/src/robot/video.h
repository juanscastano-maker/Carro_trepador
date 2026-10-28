// Cámara OV2640 y servidor de video HTTP MJPEG en el núcleo 0 (ver docs/arquitectura).
//
//   http://<ip>/            página con el video
//   http://<ip>:81/stream   video MJPEG (lo abre la GUI con el parámetro url_video)
//   http://<ip>/foto        una foto JPEG
//
// El servidor de la ESP32 atiende un solo cliente de video a la vez.
#pragma once

#include <stdint.h>

namespace video {
// Inicia la cámara (requiere PSRAM). Devuelve false si no responde.
bool iniciarCamara();
// Inicia los servidores HTTP (llamar con el Wi-Fi ya conectado).
void iniciarServidores();
// Cuadros enviados desde el arranque (para medir cuadros por segundo).
uint32_t cuadrosEnviados();
}  // namespace video
