// Prueba de la cámara OV2640 con video HTTP MJPEG.
//
// Red Wi-Fi:
//   - Si existe include/credenciales_wifi.h (copiar desde credenciales_wifi.ejemplo.h), se conecta
//     a tu red y muestra la IP por el monitor serie.
//   - Si no existe, crea su propia red "CarroTrepador-CAM" (clave "trepador123"); conectarse a
//     ella y abrir http://192.168.4.1
//
// En el navegador:
//   http://<ip>/          página con el video
//   http://<ip>:81/stream video MJPEG (solo un cliente a la vez, ver docs/arquitectura)
//   http://<ip>/foto      una foto JPEG
//
// Como en la arquitectura, el servidor de video corre en el núcleo 0 y deja libre el núcleo 1
// para el control del robot.
//
// Uso: pio run -e prueba_camara -t upload && pio device monitor
#include <Arduino.h>
#include <WiFi.h>

#include "esp_camera.h"
#include "esp_http_server.h"
#include "pines.h"

#if __has_include("credenciales_wifi.h")
#include "credenciales_wifi.h"
#define USAR_RED_PROPIA 0
#else
#define USAR_RED_PROPIA 1
#endif

namespace {
constexpr char AP_SSID[] = "CarroTrepador-CAM";
constexpr char AP_CLAVE[] = "trepador123";

#define LIMITE "carrotrepadorframe"
constexpr char TIPO_STREAM[] = "multipart/x-mixed-replace;boundary=" LIMITE;
constexpr char SEPARADOR[] = "\r\n--" LIMITE "\r\n";
constexpr char CABECERA_PARTE[] = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

volatile uint32_t cuadros_enviados = 0;

bool iniciarCamara() {
  camera_config_t c = {};
  c.pin_pwdn = CAM_PIN_PWDN;
  c.pin_reset = CAM_PIN_RESET;
  c.pin_xclk = CAM_PIN_XCLK;
  c.pin_sccb_sda = CAM_PIN_SIOD;
  c.pin_sccb_scl = CAM_PIN_SIOC;
  c.pin_d7 = CAM_PIN_Y9;
  c.pin_d6 = CAM_PIN_Y8;
  c.pin_d5 = CAM_PIN_Y7;
  c.pin_d4 = CAM_PIN_Y6;
  c.pin_d3 = CAM_PIN_Y5;
  c.pin_d2 = CAM_PIN_Y4;
  c.pin_d1 = CAM_PIN_Y3;
  c.pin_d0 = CAM_PIN_Y2;
  c.pin_vsync = CAM_PIN_VSYNC;
  c.pin_href = CAM_PIN_HREF;
  c.pin_pclk = CAM_PIN_PCLK;
  c.xclk_freq_hz = 20000000;
  c.ledc_timer = static_cast<ledc_timer_t>(LEDC_CAMARA_TIMER);
  c.ledc_channel = static_cast<ledc_channel_t>(LEDC_CAMARA_CANAL);
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA;      // 640x480; bajar a FRAMESIZE_QVGA si el Wi-Fi va lento
  c.jpeg_quality = 12;               // 10-63: menor número = mejor calidad y archivos más grandes
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;  // siempre el cuadro más reciente: menos retraso

  const esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] La cámara no inició (0x%x). Revisar el cable plano y que la PSRAM esté activa.\n",
                  err);
    return false;
  }
  sensor_t* s = esp_camera_sensor_get();
  Serial.printf("Cámara lista: sensor PID 0x%02X (0x26 = OV2640)\n", s->id.PID);
  return true;
}

esp_err_t manejarStream(httpd_req_t* req) {
  esp_err_t res = httpd_resp_set_type(req, TIPO_STREAM);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char cabecera[64];
  while (res == ESP_OK) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("[ERROR] No se pudo capturar un cuadro.");
      res = ESP_FAIL;
      break;
    }
    const size_t n = snprintf(cabecera, sizeof(cabecera), CABECERA_PARTE, fb->len);
    res = httpd_resp_send_chunk(req, SEPARADOR, strlen(SEPARADOR));
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, cabecera, n);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, reinterpret_cast<const char*>(fb->buf), fb->len);
    esp_camera_fb_return(fb);
    if (res == ESP_OK) cuadros_enviados++;
  }
  return res;  // termina cuando el navegador se desconecta
}

esp_err_t manejarFoto(httpd_req_t* req) {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) return httpd_resp_send_500(req);
  httpd_resp_set_type(req, "image/jpeg");
  const esp_err_t res = httpd_resp_send(req, reinterpret_cast<const char*>(fb->buf), fb->len);
  esp_camera_fb_return(fb);
  return res;
}

esp_err_t manejarInicio(httpd_req_t* req) {
  static const char pagina[] =
      "<!doctype html><html><head><meta name='viewport' content='width=device-width'>"
      "<title>Carro Trepador - Camara</title></head>"
      "<body style='margin:0;background:#111;color:#eee;font-family:sans-serif;text-align:center'>"
      "<h3>Carro Trepador - prueba de camara</h3>"
      "<img id='v' style='max-width:100%'>"
      "<p><a style='color:#8cf' href='/foto'>Tomar foto</a></p>"
      "<script>document.getElementById('v').src='http://'+location.hostname+':81/stream'</script>"
      "</body></html>";
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, pagina, HTTPD_RESP_USE_STRLEN);
}

void iniciarServidores() {
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.core_id = 0;  // núcleo 0, como en la arquitectura
  cfg.server_port = 80;
  cfg.ctrl_port = 32768;
  httpd_handle_t web = nullptr;
  if (httpd_start(&web, &cfg) == ESP_OK) {
    httpd_uri_t inicio = {"/", HTTP_GET, manejarInicio, nullptr};
    httpd_uri_t foto = {"/foto", HTTP_GET, manejarFoto, nullptr};
    httpd_register_uri_handler(web, &inicio);
    httpd_register_uri_handler(web, &foto);
  }

  httpd_config_t cfg_video = HTTPD_DEFAULT_CONFIG();
  cfg_video.core_id = 0;
  cfg_video.server_port = 81;
  cfg_video.ctrl_port = 32769;
  httpd_handle_t video = nullptr;
  if (httpd_start(&video, &cfg_video) == ESP_OK) {
    httpd_uri_t stream = {"/stream", HTTP_GET, manejarStream, nullptr};
    httpd_register_uri_handler(video, &stream);
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=== Prueba de cámara (OV2640) ===");
  Serial.printf("PSRAM: %u bytes %s\n", ESP.getPsramSize(),
                ESP.getPsramSize() ? "" : "<- SIN PSRAM: revisar platformio.ini (memory_type qio_opi)");
  if (!iniciarCamara()) return;

#if USAR_RED_PROPIA
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_CLAVE);
  Serial.printf("Red propia: '%s' (clave '%s'). Abrir http://%s\n", AP_SSID, AP_CLAVE,
                WiFi.softAPIP().toString().c_str());
#else
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // sin ahorro de energía: el video va más fluido
  WiFi.begin(WIFI_SSID, WIFI_CLAVE);
  Serial.printf("Conectando a '%s'", WIFI_SSID);
  const uint32_t inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[ERROR] No se pudo conectar. Revisar nombre y clave en credenciales_wifi.h.");
    return;
  }
  Serial.printf("\nConectado. Abrir http://%s  (video directo: http://%s:81/stream)\n",
                WiFi.localIP().toString().c_str(), WiFi.localIP().toString().c_str());
#endif
  iniciarServidores();
}

void loop() {
  static uint32_t ultimo = 0, cuadros_antes = 0;
  if (millis() - ultimo >= 5000) {
    const uint32_t c = cuadros_enviados;
    if (c != cuadros_antes) {
      Serial.printf("Video: %.1f cuadros/s\n", (c - cuadros_antes) / ((millis() - ultimo) / 1000.0f));
    }
    cuadros_antes = c;
    ultimo = millis();
  }
  delay(10);
}
