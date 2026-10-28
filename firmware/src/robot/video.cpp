#include "video.h"

#include <Arduino.h>

#include "esp_camera.h"
#include "esp_http_server.h"
#include "pines.h"

namespace {
#define LIMITE "carrotrepadorframe"
constexpr char TIPO_STREAM[] = "multipart/x-mixed-replace;boundary=" LIMITE;
constexpr char SEPARADOR[] = "\r\n--" LIMITE "\r\n";
constexpr char CABECERA_PARTE[] = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

volatile uint32_t cuadros_enviados = 0;

esp_err_t manejarStream(httpd_req_t* req) {
  esp_err_t res = httpd_resp_set_type(req, TIPO_STREAM);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char cabecera[64];
  while (res == ESP_OK) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
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
  return res;  // termina cuando el cliente se desconecta
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
      "<h3>Carro Trepador</h3><img id='v' style='max-width:100%'>"
      "<p><a style='color:#8cf' href='/foto'>Tomar foto</a></p>"
      "<script>document.getElementById('v').src='http://'+location.hostname+':81/stream'</script>"
      "</body></html>";
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, pagina, HTTPD_RESP_USE_STRLEN);
}
}  // namespace

namespace video {

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
  c.frame_size = FRAMESIZE_VGA;  // 640x480; bajar a FRAMESIZE_QVGA si el Wi-Fi va lento
  c.jpeg_quality = 12;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;
  return esp_camera_init(&c) == ESP_OK;
}

void iniciarServidores() {
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.core_id = 0;  // núcleo 0: el núcleo 1 queda para el control (loop de Arduino)
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
  httpd_handle_t servidor_video = nullptr;
  if (httpd_start(&servidor_video, &cfg_video) == ESP_OK) {
    httpd_uri_t stream = {"/stream", HTTP_GET, manejarStream, nullptr};
    httpd_register_uri_handler(servidor_video, &stream);
  }
}

uint32_t cuadrosEnviados() { return cuadros_enviados; }

}  // namespace video
