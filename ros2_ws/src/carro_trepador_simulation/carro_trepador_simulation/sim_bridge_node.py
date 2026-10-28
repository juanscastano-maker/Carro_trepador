"""
Puente de simulación (sim_bridge_node): reemplaza al firmware de la ESP32 en Gazebo.

Recibe los mismos tópicos que micro_ros_esp32_node y se comporta igual que el firmware:
  /cmd_motors          velocidad de cada lado [izq, der] -> tracción en Gazebo (/sim/cmd_vel)
  /cmd_suction/front   potencia de las turbinas (por ahora solo afecta el consumo de batería;
  /cmd_suction/rear    el modelo de adhesión está pendiente)
  /heartbeat           watchdog de 500 ms: sin heartbeat entra en modo seguro
  /e_stop              parada de emergencia del operador (queda enclavada hasta recibir False)
Publica:
  /battery/state       batería LiPo HV 4S simulada (voltaje, corriente y porcentaje)
  /diagnostics         estado simulado de cada componente del hardware

Ver docs/simulacion/Simulacion_Carro_trepador_v2.docx y la arquitectura v4.
"""

import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, Imu
from std_msgs.msg import Bool, Float32, Float32MultiArray, UInt32

# Curva aproximada de voltaje en reposo por celda de una LiPo HV (carga -> voltios).
# Es orientativa: se debe calibrar con una descarga real de la batería.
CURVA_LIPO_HV = [(0.00, 3.30), (0.05, 3.55), (0.10, 3.65), (0.20, 3.72), (0.30, 3.76),
                 (0.40, 3.80), (0.50, 3.84), (0.60, 3.89), (0.70, 3.96), (0.80, 4.05),
                 (0.90, 4.17), (1.00, 4.35)]


def voltaje_celda(carga):
    """Voltaje en reposo de una celda para una carga entre 0 y 1 (interpolación lineal)."""
    carga = min(max(carga, 0.0), 1.0)
    for (c0, v0), (c1, v1) in zip(CURVA_LIPO_HV, CURVA_LIPO_HV[1:]):
        if carga <= c1:
            return v0 + (v1 - v0) * (carga - c0) / (c1 - c0)
    return CURVA_LIPO_HV[-1][1]


class SimBridgeNode(Node):
    """Firmware simulado: tracción, watchdog, parada, batería y diagnósticos."""

    def __init__(self):
        super().__init__('sim_bridge_node')
        self.separacion = self.declare_parameter('separacion_ruedas', 0.1658).value
        self.v_max = self.declare_parameter('velocidad_max_rueda', 0.47).value
        self.capacidad_ah = self.declare_parameter('capacidad_ah', 1.1).value
        self.carga = self.declare_parameter('carga_inicial', 0.95).value
        # >1 hace que la batería se descargue más rápido, para probar las notificaciones
        self.acelerar_bateria = self.declare_parameter('acelerar_bateria', 1.0).value
        self.celdas = 4
        self.r_interna = 0.06  # ohmios, paquete completo

        self.motores = [0.0, 0.0]
        self.succion = {'front': 0.0, 'rear': 0.0}
        self.t_motores = 0.0
        self.t_heartbeat = None
        self.t_imu = {'front': 0.0, 'rear': 0.0}
        self.cabeceo_trasero = 0.0
        self.e_stop = False
        self.modo_seguro = False
        self.ultimo = time.monotonic()
        self.corriente = 0.0

        self.pub_vel = self.create_publisher(Twist, '/sim/cmd_vel', 10)
        self.pub_bateria = self.create_publisher(BatteryState, '/battery/state', 10)
        self.pub_diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)

        self.create_subscription(Float32MultiArray, '/cmd_motors', self.al_cmd_motors, 10)
        self.create_subscription(Float32, '/cmd_suction/front',
                                 lambda m: self.al_succion('front', m), 10)
        self.create_subscription(Float32, '/cmd_suction/rear',
                                 lambda m: self.al_succion('rear', m), 10)
        self.create_subscription(UInt32, '/heartbeat', self.al_heartbeat, 10)
        self.create_subscription(Bool, '/e_stop', self.al_e_stop, 10)
        self.create_subscription(Imu, '/imu/front/data', lambda m: self.al_imu('front', m), 10)
        self.create_subscription(Imu, '/imu/rear/data', lambda m: self.al_imu('rear', m), 10)

        self.create_timer(0.05, self.ciclo_control)   # 20 Hz, como el lazo del firmware
        self.create_timer(0.5, self.publicar_bateria)
        self.create_timer(1.0, self.publicar_diagnosticos)
        self.get_logger().info('sim_bridge_node listo: reemplaza al firmware en la simulación')

    # ---------- Entradas ----------
    def al_cmd_motors(self, msg):
        if len(msg.data) == 2:
            self.motores = [max(-1.0, min(1.0, float(v))) for v in msg.data]
            self.t_motores = time.monotonic()

    def al_succion(self, modulo, msg):
        self.succion[modulo] = max(0.0, min(100.0, float(msg.data)))

    def al_heartbeat(self, _msg):
        self.t_heartbeat = time.monotonic()

    def al_e_stop(self, msg):
        if msg.data != self.e_stop:
            self.e_stop = msg.data
            self.get_logger().warn('Parada de emergencia ' + ('ACTIVADA' if msg.data else 'liberada'))
            self.publicar_diagnosticos()

    def al_imu(self, modulo, msg):
        self.t_imu[modulo] = time.monotonic()
        if modulo == 'rear':
            a = msg.linear_acceleration
            self.cabeceo_trasero = math.degrees(math.atan2(a.x, math.hypot(a.y, a.z)))

    # ---------- Lazo de control (como el firmware) ----------
    def ciclo_control(self):
        ahora = time.monotonic()
        sin_heartbeat = self.t_heartbeat is None or ahora - self.t_heartbeat > 0.5
        if sin_heartbeat != self.modo_seguro:
            self.modo_seguro = sin_heartbeat
            if self.t_heartbeat is not None or not sin_heartbeat:
                self.get_logger().warn('Modo seguro ' + ('ACTIVADO: sin heartbeat' if sin_heartbeat
                                                         else 'desactivado: heartbeat recuperado'))
            self.publicar_diagnosticos()

        izq, der = self.motores
        if self.e_stop or self.modo_seguro or ahora - self.t_motores > 0.5:
            izq = der = 0.0
        # Modo seguro: succión al máximo. Parada: al máximo en pared, apagada en el suelo.
        if self.modo_seguro or (self.e_stop and abs(self.cabeceo_trasero) > 45.0):
            succion = {'front': 100.0, 'rear': 100.0}
        elif self.e_stop:
            succion = {'front': 0.0, 'rear': 0.0}
        else:
            succion = self.succion

        tw = Twist()
        tw.linear.x = (izq + der) / 2.0 * self.v_max
        tw.angular.z = (der - izq) * self.v_max / self.separacion
        self.pub_vel.publish(tw)

        # Consumo: electrónica + 4 motores N20 + 2 turbinas (crece con el cubo de la potencia)
        self.corriente = (0.4 + 0.5 * (abs(izq) + abs(der))
                          + sum(17.0 * (p / 100.0) ** 3 for p in succion.values()))
        dt = ahora - self.ultimo
        self.ultimo = ahora
        self.carga -= self.corriente * dt / 3600.0 / self.capacidad_ah * self.acelerar_bateria
        self.carga = max(self.carga, 0.0)

    # ---------- Salidas ----------
    def publicar_bateria(self):
        v_reposo = voltaje_celda(self.carga) * self.celdas
        b = BatteryState()
        b.header.stamp = self.get_clock().now().to_msg()
        b.voltage = float(v_reposo - self.corriente * self.r_interna)
        b.current = float(-self.corriente)  # convención de ROS: negativa al descargar
        b.charge = float(self.carga * self.capacidad_ah)
        b.capacity = float(self.capacidad_ah)
        b.design_capacity = float(self.capacidad_ah)
        b.percentage = float(self.carga)    # convención de ROS: de 0 a 1
        b.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        b.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO
        b.present = True
        b.cell_voltage = [float(b.voltage / self.celdas)] * self.celdas
        self.pub_bateria.publish(b)

    def publicar_diagnosticos(self):
        ahora = time.monotonic()
        estados = []

        def estado(nombre, nivel, mensaje, **valores):
            s = DiagnosticStatus(name=nombre, level=nivel, message=mensaje, hardware_id='simulacion')
            s.values = [KeyValue(key=k, value=str(v)) for k, v in valores.items()]
            estados.append(s)

        for modulo, nombre in [('front', 'IMU delantera'), ('rear', 'IMU trasera')]:
            sin_datos = ahora - self.t_imu[modulo] > 0.2
            estado(nombre, DiagnosticStatus.ERROR if sin_datos else DiagnosticStatus.OK,
                   'sin datos' if sin_datos else 'ok')
        estado('DRV8833', DiagnosticStatus.OK, 'ok', izquierda=round(self.motores[0], 2),
               derecha=round(self.motores[1], 2))
        estado('INA226', DiagnosticStatus.OK, 'ok', corriente_a=round(self.corriente, 2))
        estado('ESC delantero', DiagnosticStatus.OK, 'ok', potencia=self.succion['front'])
        estado('ESC trasero', DiagnosticStatus.OK, 'ok', potencia=self.succion['rear'])
        estado('Watchdog', DiagnosticStatus.WARN if self.modo_seguro else DiagnosticStatus.OK,
               'modo seguro: sin heartbeat' if self.modo_seguro else 'heartbeat ok')
        estado('Parada de emergencia', DiagnosticStatus.WARN if self.e_stop else DiagnosticStatus.OK,
               'activa' if self.e_stop else 'inactiva')

        arr = DiagnosticArray()
        arr.header.stamp = self.get_clock().now().to_msg()
        arr.status = estados
        self.pub_diag.publish(arr)


def main(args=None):
    rclpy.init(args=args)
    node = SimBridgeNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
