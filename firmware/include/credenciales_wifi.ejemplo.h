// Plantilla de credenciales Wi-Fi.
// Copiar este archivo como "credenciales_wifi.h" (en esta misma carpeta) y poner los datos
// de tu red. credenciales_wifi.h está en el .gitignore: tu contraseña no se sube a GitHub.
//
// Si credenciales_wifi.h no existe, la prueba de cámara crea su propia red Wi-Fi
// (punto de acceso) con el nombre y la clave de abajo.
#pragma once

#define WIFI_SSID "nombre_de_tu_red"
#define WIFI_CLAVE "clave_de_tu_red"

// IP del PC donde corre el agente de micro-ROS (con comas, no puntos) y su puerto UDP.
// Ver la IP del PC con: hostname -I
#define AGENTE_IP 192, 168, 1, 100
#define AGENTE_PUERTO 8888
