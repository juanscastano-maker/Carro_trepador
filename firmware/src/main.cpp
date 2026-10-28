// Firmware del Carro Trepador (micro_ros_esp32_node) para la ESP32-S3 CAM N16R8.
// Arquitectura: docs/arquitectura/Arquitectura_Carro_trepador_v5.docx
// Conexiones:   docs/electronica/Conexiones_Carro_trepador_v3.docx
//
// Núcleo 1 (loop de Arduino): micro-ROS, IMUs, batería, motores N20 y turbinas.
// Núcleo 0: Wi-Fi y servidor de video HTTP MJPEG (http://<ip>:81/stream).
//
// Publica:  /imu/front/data, /imu/rear/data (sensor_msgs/Imu, 50 Hz)
//           /battery/state (sensor_msgs/BatteryState, 2 Hz)
// Recibe:   /cmd_motors (Float32MultiArray [izq, der], -1..1)
//           /cmd_suction/front, /cmd_suction/rear (Float32, 0..100 %)
//           /heartbeat (UInt32, del supervisor), /e_stop (Bool, del operador)
//
// Seguridad (la decide el firmware, no depende del PC):
//   - Sin heartbeat por 500 ms (supervisor caído o Wi-Fi perdido): MODO SEGURO.
//   - Parada de emergencia del operador: PARADA.
//   En los dos casos la tracción se detiene de inmediato. Las turbinas van al máximo si el
//   robot NO está en el suelo (para que quede pegado) y se apagan si está en el suelo.
//   - Al encender, hasta recibir el primer heartbeat, nada se mueve (ESPERANDO).
//
// Requiere include/credenciales_wifi.h (copiar de credenciales_wifi.ejemplo.h) con la red y la
// IP del PC donde corre el agente de micro-ROS.
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <micro_ros_platformio.h>
#include <rcl/rcl.h>
#include <rclc/executor.h>
#include <rclc/rclc.h>
#include <rmw_microros/rmw_microros.h>
#include <sensor_msgs/msg/battery_state.h>
#include <sensor_msgs/msg/imu.h>
#include <std_msgs/msg/bool.h>
#include <std_msgs/msg/float32.h>
#include <std_msgs/msg/float32_multi_array.h>
#include <std_msgs/msg/u_int32.h>

#include "Drv8833.h"
#include "EscPwm.h"
#include "FiltroOrientacion.h"
#include "Ina226.h"
#include "Mpu6050.h"
#include "robot/video.h"
#include "pines.h"

#if __has_include("credenciales_wifi.h")
#include "credenciales_wifi.h"
#else
#error "Falta include/credenciales_wifi.h: copiar credenciales_wifi.ejemplo.h y poner la red y la IP del agente."
#endif

// Las funciones de rcl avisan si se ignora su resultado; aquí no hay nada que hacer si fallan
#define IGNORAR(x) \
  do {             \
    if (x) {       \
    }              \
  } while (0)

namespace {
// ============================================================ ajustes
constexpr uint32_t TIMEOUT_HEARTBEAT_MS = 500;
constexpr uint32_t TIMEOUT_CMD_MOTORES_MS = 500;  // sin órdenes de motores: frenar suave
constexpr uint32_t PERIODO_IMU_MS = 20;           // 50 Hz hacia ROS (el filtro corre a 100 Hz)
constexpr uint32_t PERIODO_BATERIA_MS = 500;      // 2 Hz
constexpr float INCLINACION_SUELO = 25.0f;        // grados: igual que el supervisor

// Motores N20: fracción de velocidad máxima por segundo
constexpr float MOTOR_ACELERACION = 1.0f;
constexpr float MOTOR_FRENADO = 2.0f;
// Turbinas: subir rápido (agarre) y bajar más despacio
constexpr float TURBINA_SUBIDA = 0.8f;
constexpr float TURBINA_BAJADA = 0.4f;
// Tope del acelerador de las turbinas (0 a 1). Bajarlo para las primeras pruebas.
constexpr float TURBINA_TOPE = 1.0f;

// Batería LiPo HV 4S 1100 mAh y shunt externo de 1 mΩ (ver documento de conexiones)
constexpr int CELDAS = 4;
constexpr float CAPACIDAD_AH = 1.1f;
constexpr float R_SHUNT = 0.001f;
constexpr float CORRIENTE_MAX = 80.0f;
constexpr float R_INTERNA = 0.06f;           // ohmios del paquete: corrige la caída con carga
constexpr float ALERTA_BAJO_VOLTAJE = 14.0f;  // 3.5 V por celda
// Voltaje en reposo por celda de una LiPo HV -> carga (0 a 1)
constexpr float CURVA[][2] = {{3.30f, 0.00f}, {3.55f, 0.05f}, {3.65f, 0.10f}, {3.72f, 0.20f},
                              {3.76f, 0.30f}, {3.80f, 0.40f}, {3.84f, 0.50f}, {3.89f, 0.60f},
                              {3.96f, 0.70f}, {4.05f, 0.80f}, {4.17f, 0.90f}, {4.35f, 1.00f}};

const IPAddress AGENTE(AGENTE_IP);

// ============================================================ hardware
Mpu6050 imu_del, imu_tras;
FiltroOrientacion filtro_del, filtro_tras;
LecturaImu lectura_del{}, lectura_tras{};
bool ok_imu_del = false, ok_imu_tras = false, ok_ina = false, ok_camara = false;
uint32_t us_imu_del = 0, us_imu_tras = 0;
Ina226 ina;
Drv8833 drv(MOTOR_ACELERACION, MOTOR_FRENADO);
EscPwm esc_del(TURBINA_SUBIDA, TURBINA_BAJADA), esc_tras(TURBINA_SUBIDA, TURBINA_BAJADA);
volatile bool alerta = false;
void IRAM_ATTR alBajarAlerta() { alerta = true; }

// ============================================================ estado
enum class Modo { Esperando, Normal, Parada, Seguro };
Modo modo = Modo::Esperando;
bool e_stop = false;
uint32_t ms_heartbeat = 0, ms_cmd_motores = 0;
bool hubo_heartbeat = false;
float cmd_izq = 0, cmd_der = 0, cmd_succion_del = 0, cmd_succion_tras = 0;  // succión 0..1
float carga = -1;  // 0..1, -1 = sin estimar todavía

// ============================================================ micro-ROS
rcl_allocator_t allocator;
rclc_support_t support;
rcl_node_t nodo;
rclc_executor_t executor;
rcl_publisher_t pub_imu_del, pub_imu_tras, pub_bateria;
rcl_subscription_t sub_motores, sub_succion_del, sub_succion_tras, sub_heartbeat, sub_e_stop;
sensor_msgs__msg__Imu msg_imu_del, msg_imu_tras;
sensor_msgs__msg__BatteryState msg_bateria;
std_msgs__msg__Float32MultiArray msg_motores;
float buffer_motores[4];
std_msgs__msg__Float32 msg_succion_del, msg_succion_tras;
std_msgs__msg__UInt32 msg_heartbeat;
std_msgs__msg__Bool msg_e_stop;
float celdas_bateria[CELDAS];

enum class Agente { Esperando, Disponible, Conectado, Desconectado };
Agente agente = Agente::Esperando;

// ------------------------------------------------------------ callbacks de ROS
void alRecibirMotores(const void* m) {
  const auto* msg = static_cast<const std_msgs__msg__Float32MultiArray*>(m);
  if (msg->data.size < 2) return;
  cmd_izq = constrain(msg->data.data[0], -1.0f, 1.0f);
  cmd_der = constrain(msg->data.data[1], -1.0f, 1.0f);
  ms_cmd_motores = millis();
}

void alRecibirSuccionDel(const void* m) {
  cmd_succion_del = constrain(static_cast<const std_msgs__msg__Float32*>(m)->data, 0.0f, 100.0f) / 100.0f;
}

void alRecibirSuccionTras(const void* m) {
  cmd_succion_tras = constrain(static_cast<const std_msgs__msg__Float32*>(m)->data, 0.0f, 100.0f) / 100.0f;
}

void alRecibirHeartbeat(const void*) {
  ms_heartbeat = millis();
  hubo_heartbeat = true;
}

void alRecibirEStop(const void* m) {
  const bool nuevo = static_cast<const std_msgs__msg__Bool*>(m)->data;
  if (nuevo != e_stop) Serial.printf("Parada de emergencia %s\n", nuevo ? "ACTIVADA" : "liberada");
  e_stop = nuevo;
  if (e_stop) drv.frenarYa();  // sin esperar a la siguiente vuelta del loop
}

// ------------------------------------------------------------ mensajes
void prepararImu(sensor_msgs__msg__Imu& msg, const char* marco) {
  sensor_msgs__msg__Imu__init(&msg);
  msg.header.frame_id.data = const_cast<char*>(marco);
  msg.header.frame_id.size = strlen(marco);
  msg.header.frame_id.capacity = msg.header.frame_id.size + 1;
  // Varianzas aproximadas del MPU6050 con el filtro de 44 Hz. El rumbo (yaw) no se conoce: -1 no
  // sirve aquí porque eso indicaría "sin orientación"; se pone una varianza enorme en z.
  msg.orientation_covariance[0] = msg.orientation_covariance[4] = 0.0012;
  msg.orientation_covariance[8] = 1e6;
  msg.angular_velocity_covariance[0] = msg.angular_velocity_covariance[4] =
      msg.angular_velocity_covariance[8] = 4e-5;
  msg.linear_acceleration_covariance[0] = msg.linear_acceleration_covariance[4] =
      msg.linear_acceleration_covariance[8] = 0.0025;
}

void sellarTiempo(builtin_interfaces__msg__Time& t) {
  const int64_t ns = rmw_uros_epoch_nanos();
  t.sec = static_cast<int32_t>(ns / 1000000000LL);
  t.nanosec = static_cast<uint32_t>(ns % 1000000000LL);
}

void llenarImu(sensor_msgs__msg__Imu& msg, const LecturaImu& l, const FiltroOrientacion& f) {
  sellarTiempo(msg.header.stamp);
  msg.orientation.w = f.w();
  msg.orientation.x = f.x();
  msg.orientation.y = f.y();
  msg.orientation.z = f.z();
  msg.angular_velocity.x = l.gx;
  msg.angular_velocity.y = l.gy;
  msg.angular_velocity.z = l.gz;
  msg.linear_acceleration.x = l.ax;
  msg.linear_acceleration.y = l.ay;
  msg.linear_acceleration.z = l.az;
}

// ------------------------------------------------------------ entidades de micro-ROS
#define VERIFICAR(fn)              \
  if ((fn) != RCL_RET_OK) {        \
    Serial.println("[ERROR] " #fn); \
    return false;                  \
  }

bool crearEntidades() {
  allocator = rcl_get_default_allocator();
  VERIFICAR(rclc_support_init(&support, 0, nullptr, &allocator));
  VERIFICAR(rclc_node_init_default(&nodo, "micro_ros_esp32_node", "", &support));

  // Sensores en "best effort" (como sensor_data en ROS): si se pierde una muestra por Wi-Fi no
  // se reenvía, llega la siguiente. Los nodos del PC se suscriben con qos_profile_sensor_data.
  const auto* tipo_imu = ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu);
  VERIFICAR(rclc_publisher_init_best_effort(&pub_imu_del, &nodo, tipo_imu, "/imu/front/data"));
  VERIFICAR(rclc_publisher_init_best_effort(&pub_imu_tras, &nodo, tipo_imu, "/imu/rear/data"));
  VERIFICAR(rclc_publisher_init_best_effort(&pub_bateria, &nodo,
                                            ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, BatteryState),
                                            "/battery/state"));

  // Órdenes: la parada es confiable (no se puede perder); las demás llegan muchas veces por
  // segundo y van en best effort.
  const auto* tipo_f32 = ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32);
  VERIFICAR(rclc_subscription_init_best_effort(&sub_motores, &nodo,
                                               ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32MultiArray),
                                               "/cmd_motors"));
  VERIFICAR(rclc_subscription_init_best_effort(&sub_succion_del, &nodo, tipo_f32, "/cmd_suction/front"));
  VERIFICAR(rclc_subscription_init_best_effort(&sub_succion_tras, &nodo, tipo_f32, "/cmd_suction/rear"));
  VERIFICAR(rclc_subscription_init_best_effort(&sub_heartbeat, &nodo,
                                               ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, UInt32), "/heartbeat"));
  VERIFICAR(rclc_subscription_init_default(&sub_e_stop, &nodo, ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool),
                                           "/e_stop"));

  executor = rclc_executor_get_zero_initialized_executor();
  VERIFICAR(rclc_executor_init(&executor, &support.context, 5, &allocator));
  VERIFICAR(rclc_executor_add_subscription(&executor, &sub_e_stop, &msg_e_stop, alRecibirEStop, ON_NEW_DATA));
  VERIFICAR(rclc_executor_add_subscription(&executor, &sub_heartbeat, &msg_heartbeat, alRecibirHeartbeat,
                                           ON_NEW_DATA));
  VERIFICAR(rclc_executor_add_subscription(&executor, &sub_motores, &msg_motores, alRecibirMotores, ON_NEW_DATA));
  VERIFICAR(rclc_executor_add_subscription(&executor, &sub_succion_del, &msg_succion_del, alRecibirSuccionDel,
                                           ON_NEW_DATA));
  VERIFICAR(rclc_executor_add_subscription(&executor, &sub_succion_tras, &msg_succion_tras, alRecibirSuccionTras,
                                           ON_NEW_DATA));

  rmw_uros_sync_session(1000);  // reloj sincronizado con el PC para las marcas de tiempo
  return true;
}

void destruirEntidades() {
  rmw_context_t* ctx = rcl_context_get_rmw_context(&support.context);
  (void)rmw_uros_set_context_entity_destroy_session_timeout(ctx, 0);
  IGNORAR(rcl_publisher_fini(&pub_imu_del, &nodo));
  IGNORAR(rcl_publisher_fini(&pub_imu_tras, &nodo));
  IGNORAR(rcl_publisher_fini(&pub_bateria, &nodo));
  IGNORAR(rcl_subscription_fini(&sub_motores, &nodo));
  IGNORAR(rcl_subscription_fini(&sub_succion_del, &nodo));
  IGNORAR(rcl_subscription_fini(&sub_succion_tras, &nodo));
  IGNORAR(rcl_subscription_fini(&sub_heartbeat, &nodo));
  IGNORAR(rcl_subscription_fini(&sub_e_stop, &nodo));
  IGNORAR(rclc_executor_fini(&executor));
  IGNORAR(rcl_node_fini(&nodo));
  IGNORAR(rclc_support_fini(&support));
}

// Reconexión con el agente: si el PC se cae o se reinicia el agente, el firmware vuelve a
// conectarse solo. Mientras tanto no llega heartbeat y el robot queda en modo seguro.
void atenderAgente() {
  static uint32_t ultimo_ping = 0;
  const uint32_t ahora = millis();
  switch (agente) {
    case Agente::Esperando:
      if (ahora - ultimo_ping > 500) {
        ultimo_ping = ahora;
        if (rmw_uros_ping_agent(100, 1) == RMW_RET_OK) agente = Agente::Disponible;
      }
      break;
    case Agente::Disponible:
      if (crearEntidades()) {
        agente = Agente::Conectado;
        Serial.println("Conectado al agente de micro-ROS.");
      } else {
        destruirEntidades();
        agente = Agente::Esperando;
      }
      break;
    case Agente::Conectado:
      if (ahora - ultimo_ping > 1000) {
        ultimo_ping = ahora;
        if (rmw_uros_ping_agent(100, 3) != RMW_RET_OK) {
          agente = Agente::Desconectado;
          break;
        }
      }
      IGNORAR(rclc_executor_spin_some(&executor, RCL_MS_TO_NS(1)));
      break;
    case Agente::Desconectado:
      Serial.println("Se perdió el agente de micro-ROS. Reintentando...");
      destruirEntidades();
      agente = Agente::Esperando;
      break;
  }
}

// ============================================================ batería
float cargaPorVoltaje(float v_celda) {
  constexpr int n = sizeof(CURVA) / sizeof(CURVA[0]);
  if (v_celda <= CURVA[0][0]) return 0.0f;
  for (int i = 1; i < n; i++) {
    if (v_celda <= CURVA[i][0]) {
      const float f = (v_celda - CURVA[i - 1][0]) / (CURVA[i][0] - CURVA[i - 1][0]);
      return CURVA[i - 1][1] + f * (CURVA[i][1] - CURVA[i - 1][1]);
    }
  }
  return 1.0f;
}

void publicarBateria() {
  LecturaPotencia l{};
  msg_bateria.present = ok_ina && ina.leer(l);
  sellarTiempo(msg_bateria.header.stamp);
  if (msg_bateria.present) {
    // Voltaje en reposo estimado: la caída por la resistencia interna se suma de vuelta
    const float estimada = cargaPorVoltaje((l.voltaje + l.corriente * R_INTERNA) / CELDAS);
    carga = carga < 0 ? estimada : carga + 0.05f * (estimada - carga);  // suavizado
    msg_bateria.voltage = l.voltaje;
    msg_bateria.current = -l.corriente;  // convención de ROS: negativa al descargar
    msg_bateria.percentage = carga;
    msg_bateria.charge = carga * CAPACIDAD_AH;
    for (int i = 0; i < CELDAS; i++) celdas_bateria[i] = l.voltaje / CELDAS;  // promedio: no hay balanceo
  } else {
    msg_bateria.voltage = msg_bateria.current = msg_bateria.percentage = msg_bateria.charge = NAN;
  }
  if (agente == Agente::Conectado) IGNORAR(rcl_publish(&pub_bateria, &msg_bateria, nullptr));
}

// ============================================================ IMUs
void leerImu(Mpu6050& imu, LecturaImu& l, FiltroOrientacion& f, uint32_t& us_anterior) {
  if (!imu.datoNuevo() || !imu.leer(l)) return;
  const uint32_t ahora = micros();
  const float dt = us_anterior ? (ahora - us_anterior) * 1e-6f : 0.01f;
  us_anterior = ahora;
  f.actualizar(l.ax, l.ay, l.az, l.gx, l.gy, l.gz, dt > 0.05f ? 0.05f : dt);
}

bool enSuelo() {
  // Con alguna IMU sin funcionar no se puede saber: se asume que NO está en el suelo (más seguro)
  if (!ok_imu_del || !ok_imu_tras || !filtro_del.iniciado() || !filtro_tras.iniciado()) return false;
  return filtro_del.inclinacion() < INCLINACION_SUELO && filtro_tras.inclinacion() < INCLINACION_SUELO;
}

// ============================================================ actuadores
void aplicarActuadores() {
  const uint32_t ahora = millis();
  Modo nuevo;
  if (!hubo_heartbeat) {
    nuevo = Modo::Esperando;
  } else if (ahora - ms_heartbeat > TIMEOUT_HEARTBEAT_MS) {
    nuevo = Modo::Seguro;
  } else if (e_stop) {
    nuevo = Modo::Parada;
  } else {
    nuevo = Modo::Normal;
  }
  if (nuevo != modo) {
    static const char* nombres[] = {"ESPERANDO heartbeat", "NORMAL", "PARADA", "MODO SEGURO (sin heartbeat)"};
    Serial.printf("Modo: %s\n", nombres[static_cast<int>(nuevo)]);
    if (nuevo != Modo::Normal) drv.frenarYa();
    modo = nuevo;
  }

  if (modo == Modo::Normal) {
    const bool vigente = ahora - ms_cmd_motores < TIMEOUT_CMD_MOTORES_MS;
    drv.fijarObjetivo(vigente ? cmd_izq : 0.0f, vigente ? cmd_der : 0.0f);
    esc_del.fijarObjetivo(cmd_succion_del);
    esc_tras.fijarObjetivo(cmd_succion_tras);
  } else {
    drv.fijarObjetivo(0, 0);
    // Esperando: todo apagado. Parada o seguro: pegado si no está en el suelo.
    const float succion = (modo != Modo::Esperando && !enSuelo()) ? 1.0f : 0.0f;
    esc_del.fijarObjetivo(succion);
    esc_tras.fijarObjetivo(succion);
  }
  drv.actualizar();
  esc_del.actualizar();
  esc_tras.actualizar();
}

void mostrarEstadoLed() {
  static uint32_t ultimo = 0;
  if (millis() - ultimo < 250) return;
  ultimo = millis();
  const bool parpadeo = (millis() / 250) % 2;
  if (agente != Agente::Conectado) {
    neopixelWrite(PIN_LED_WS2812, parpadeo ? 20 : 0, parpadeo ? 10 : 0, 0);  // naranja: sin agente
  } else if (modo == Modo::Parada || modo == Modo::Seguro) {
    neopixelWrite(PIN_LED_WS2812, 30, 0, 0);  // rojo
  } else if (modo == Modo::Esperando) {
    neopixelWrite(PIN_LED_WS2812, 0, 0, 30);  // azul: falta el supervisor
  } else {
    neopixelWrite(PIN_LED_WS2812, 0, 25, 0);  // verde: normal
  }
}

void informar() {
  static uint32_t ultimo = 0;
  if (millis() - ultimo < 2000) return;
  ultimo = millis();
  static uint32_t cuadros_antes = 0;
  const uint32_t cuadros = video::cuadrosEnviados();
  Serial.printf("[%s] motores %+.2f %+.2f | turbinas %3.0f%% %3.0f%% | inclinación del %5.1f° tras %5.1f° | "
                "batería %.2f V %.1f A | video %.1f fps\n",
                agente == Agente::Conectado ? "ROS" : "sin agente", drv.velocidadIzquierda(),
                drv.velocidadDerecha(), esc_del.acelerador() * 100, esc_tras.acelerador() * 100,
                filtro_del.inclinacion(), filtro_tras.inclinacion(), msg_bateria.voltage, -msg_bateria.current,
                (cuadros - cuadros_antes) / 2.0f);
  cuadros_antes = cuadros;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Carro Trepador: firmware con micro-ROS ===");

  // Actuadores primero: los ESC deben ver 0 % desde el principio para armarse
  esc_del.begin(PIN_ESC_DELANTERO, LEDC_ESC_DELANTERO);
  esc_tras.begin(PIN_ESC_TRASERO, LEDC_ESC_TRASERO);
  esc_del.fijarMaximo(TURBINA_TOPE);
  esc_tras.fijarMaximo(TURBINA_TOPE);
  drv.begin(PIN_DRV_SLEEP, {PIN_DRV_IN1, PIN_DRV_IN2, LEDC_DRV_IN1, LEDC_DRV_IN2, false},
            {PIN_DRV_IN3, PIN_DRV_IN4, LEDC_DRV_IN3, LEDC_DRV_IN4, false});
  drv.habilitar(true);

  // Sensores
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_FRECUENCIA);
  Wire.setTimeOut(20);
  ok_imu_del = imu_del.begin(Wire, DIR_IMU_DELANTERA, PIN_INT_IMU_DELANTERA);
  ok_imu_tras = imu_tras.begin(Wire, DIR_IMU_TRASERA, PIN_INT_IMU_TRASERA);
  Serial.printf("IMU delantera: %s | IMU trasera: %s\n", ok_imu_del ? "ok" : "NO RESPONDE",
                ok_imu_tras ? "ok" : "NO RESPONDE");
  Serial.println("Calibrando giroscopios: no mover el robot...");
  if (ok_imu_del) imu_del.calibrarGiroscopio();
  if (ok_imu_tras) imu_tras.calibrarGiroscopio();
  ok_ina = ina.begin(Wire, DIR_INA226, R_SHUNT, CORRIENTE_MAX);
  if (ok_ina) ina.alertaBajoVoltaje(ALERTA_BAJO_VOLTAJE);
  Serial.printf("INA226: %s\n", ok_ina ? "ok" : "NO RESPONDE");
  pinMode(PIN_ALERTA, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ALERTA), alBajarAlerta, FALLING);
  ok_camara = video::iniciarCamara();
  Serial.printf("Cámara: %s\n", ok_camara ? "ok" : "NO RESPONDE");

  // Mensajes
  prepararImu(msg_imu_del, "imu_front_link");
  prepararImu(msg_imu_tras, "imu_rear_link");
  sensor_msgs__msg__BatteryState__init(&msg_bateria);
  msg_bateria.capacity = msg_bateria.design_capacity = CAPACIDAD_AH;
  msg_bateria.power_supply_technology = sensor_msgs__msg__BatteryState__POWER_SUPPLY_TECHNOLOGY_LIPO;
  msg_bateria.power_supply_status = sensor_msgs__msg__BatteryState__POWER_SUPPLY_STATUS_DISCHARGING;
  msg_bateria.cell_voltage.data = celdas_bateria;
  msg_bateria.cell_voltage.size = msg_bateria.cell_voltage.capacity = CELDAS;
  msg_motores.data.data = buffer_motores;
  msg_motores.data.capacity = 4;
  msg_motores.data.size = 0;

  // Wi-Fi + transporte de micro-ROS (espera hasta conectarse a la red)
  Serial.printf("Conectando a la red '%s' (agente en %s:%d)...\n", WIFI_SSID, AGENTE.toString().c_str(),
                AGENTE_PUERTO);
  set_microros_wifi_transports(const_cast<char*>(WIFI_SSID), const_cast<char*>(WIFI_CLAVE), AGENTE,
                               AGENTE_PUERTO);
  WiFi.setSleep(false);
  Serial.printf("Wi-Fi conectado. IP del robot: %s\n", WiFi.localIP().toString().c_str());
  if (ok_camara) {
    video::iniciarServidores();
    Serial.printf("Video: http://%s:81/stream\n", WiFi.localIP().toString().c_str());
  }
}

void loop() {
  atenderAgente();

  if (ok_imu_del) leerImu(imu_del, lectura_del, filtro_del, us_imu_del);
  if (ok_imu_tras) leerImu(imu_tras, lectura_tras, filtro_tras, us_imu_tras);

  const uint32_t ahora = millis();
  static uint32_t ms_imu = 0, ms_bateria = 0;
  if (ahora - ms_imu >= PERIODO_IMU_MS) {
    ms_imu = ahora;
    if (agente == Agente::Conectado) {
      if (ok_imu_del) {
        llenarImu(msg_imu_del, lectura_del, filtro_del);
        IGNORAR(rcl_publish(&pub_imu_del, &msg_imu_del, nullptr));
      }
      if (ok_imu_tras) {
        llenarImu(msg_imu_tras, lectura_tras, filtro_tras);
        IGNORAR(rcl_publish(&pub_imu_tras, &msg_imu_tras, nullptr));
      }
    }
  }
  if (ahora - ms_bateria >= PERIODO_BATERIA_MS) {
    ms_bateria = ahora;
    publicarBateria();
  }

  if (alerta) {
    alerta = false;
    if (ok_ina && ina.alertaActiva()) {
      Serial.println("[ALERTA] INA226: batería por debajo del límite.");
    } else {
      Serial.println("[ALERTA] Falla del DRV8833 (nFAULT): sobrecorriente o sobretemperatura en los motores.");
    }
  }

  aplicarActuadores();
  mostrarEstadoLed();
  informar();
}
