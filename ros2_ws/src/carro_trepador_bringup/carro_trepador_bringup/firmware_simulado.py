#!/usr/bin/env python3
"""
Firmware simulado: hace de ESP32 en el PC para probar los nodos de ROS sin el robot.

NO es parte de la arquitectura: es una herramienta de prueba. Publica y recibe los mismos tópicos
que micro_ros_esp32_node:
  publica  /imu/front/data, /imu/rear/data (100 Hz), /battery/state (2 Hz)
  recibe   /cmd_motors, /cmd_suction/front, /cmd_suction/rear, /heartbeat, /e_stop
y las mismas reglas de seguridad que el firmware real (watchdog de 500 ms, parada y espera
del primer heartbeat).

Uso (con el workspace cargado):
  ros2 run carro_trepador_bringup firmware_simulado
  (o todo junto: ros2 launch carro_trepador_bringup bringup.launch.py simulado:=true)
Cambiar la inclinación de cada módulo en vivo (grados; 0 = suelo, 90 = pared):
  ros2 param set /firmware_simulado inclinacion_delantera 90.0
  ros2 param set /firmware_simulado inclinacion_trasera 90.0
Otros parámetros: acelerar_bateria (1.0 = tiempo real), imu_delantera_activa / imu_trasera_activa
(false simula una IMU desconectada), carga_inicial (0 a 1).
"""

import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState, Imu
from std_msgs.msg import Bool, Float32, Float32MultiArray, UInt32

G = 9.80665
# Curva aproximada de voltaje en reposo por celda de una LiPo HV (carga -> voltios)
CURVA = [(0.00, 3.30), (0.05, 3.55), (0.10, 3.65), (0.20, 3.72), (0.30, 3.76), (0.40, 3.80),
         (0.50, 3.84), (0.60, 3.89), (0.70, 3.96), (0.80, 4.05), (0.90, 4.17), (1.00, 4.35)]


def voltaje_celda(c):
    c = min(max(c, 0.0), 1.0)
    for (c0, v0), (c1, v1) in zip(CURVA, CURVA[1:]):
        if c <= c1:
            return v0 + (v1 - v0) * (c - c0) / (c1 - c0)
    return CURVA[-1][1]


class FirmwareSimulado(Node):
    def __init__(self):
        super().__init__('firmware_simulado')
        p = self.declare_parameter
        p('inclinacion_delantera', 0.0)
        p('inclinacion_trasera', 0.0)
        p('imu_delantera_activa', True)
        p('imu_trasera_activa', True)
        p('acelerar_bateria', 1.0)
        self.carga = p('carga_inicial', 0.95).value

        self.motores = [0.0, 0.0]
        self.succion = {'front': 0.0, 'rear': 0.0}
        self.t_heartbeat = None
        self.e_stop = False
        self.modo = 'ESPERANDO'
        self.corriente = 0.0
        self.ultimo = time.monotonic()

        self.pub_imu = {'front': self.create_publisher(Imu, '/imu/front/data', 10),
                        'rear': self.create_publisher(Imu, '/imu/rear/data', 10)}
        self.pub_bat = self.create_publisher(BatteryState, '/battery/state', 10)
        self.create_subscription(Float32MultiArray, '/cmd_motors', self.al_motores, 10)
        self.create_subscription(Float32, '/cmd_suction/front',
                                 lambda m: self.al_succion('front', m), 10)
        self.create_subscription(Float32, '/cmd_suction/rear',
                                 lambda m: self.al_succion('rear', m), 10)
        self.create_subscription(UInt32, '/heartbeat', self.al_heartbeat, 10)
        self.create_subscription(Bool, '/e_stop', self.al_e_stop,
                                 QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE))
        self.create_timer(0.01, self.publicar_imus)
        self.create_timer(0.05, self.ciclo)
        self.create_timer(0.5, self.publicar_bateria)
        self.create_timer(2.0, self.informe)
        self.get_logger().info('Firmware simulado listo (no es el firmware real).')

    def al_motores(self, m):
        if len(m.data) == 2:
            self.motores = list(m.data)

    def al_succion(self, modulo, m):
        self.succion[modulo] = max(0.0, min(100.0, m.data))

    def al_heartbeat(self, _m):
        self.t_heartbeat = time.monotonic()

    def al_e_stop(self, m):
        if m.data != self.e_stop:
            self.e_stop = m.data
            self.get_logger().warn('Parada de emergencia '
                                   + ('ACTIVADA' if m.data else 'liberada'))

    def imu(self, inclinacion_grados):
        """IMU con el módulo inclinado hacia adelante (cabeceo) el ángulo dado."""
        t = math.radians(inclinacion_grados)
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.linear_acceleration.x = G * math.sin(t)   # nariz arriba -> gravedad hacia +x
        msg.linear_acceleration.z = G * math.cos(t)
        # Orientación "ya calculada por el firmware": giro alrededor de y de -t (convención de ROS)
        msg.orientation.w = math.cos(-t / 2)
        msg.orientation.y = math.sin(-t / 2)
        return msg

    def publicar_imus(self):
        for modulo, nombre in (('front', 'delantera'), ('rear', 'trasera')):
            if self.get_parameter(f'imu_{nombre}_activa').value:
                msg = self.imu(self.get_parameter(f'inclinacion_{nombre}').value)
                msg.header.frame_id = f'imu_{modulo}_link'
                self.pub_imu[modulo].publish(msg)

    def ciclo(self):
        # Mismas reglas que firmware/src/main.cpp
        ahora = time.monotonic()
        if self.t_heartbeat is None:
            modo = 'ESPERANDO'
        elif ahora - self.t_heartbeat > 0.5:
            modo = 'MODO SEGURO'
        elif self.e_stop:
            modo = 'PARADA'
        else:
            modo = 'normal'
        if modo != self.modo:
            self.modo = modo
            self.get_logger().warn(f'Modo: {modo}')
        en_suelo = all(self.get_parameter(f'inclinacion_{m}').value < 25
                       for m in ('delantera', 'trasera'))
        if modo == 'normal':
            izq, der = self.motores
            succion = self.succion
        else:
            izq = der = 0.0
            # Esperando: todo apagado. Parada o seguro: pegado si no está en el suelo.
            s = 100.0 if modo != 'ESPERANDO' and not en_suelo else 0.0
            succion = {'front': s, 'rear': s}
        self.salida = (izq, der, succion)
        self.corriente = (0.4 + 0.5 * (abs(izq) + abs(der))
                          + sum(17.0 * (s / 100) ** 3 for s in succion.values()))
        dt = ahora - self.ultimo
        self.ultimo = ahora
        self.carga = max(0.0, self.carga - self.corriente * dt / 3600 / 1.1
                         * self.get_parameter('acelerar_bateria').value)

    def publicar_bateria(self):
        b = BatteryState()
        b.header.stamp = self.get_clock().now().to_msg()
        b.voltage = voltaje_celda(self.carga) * 4 - self.corriente * 0.06
        b.current = -self.corriente
        b.percentage = self.carga
        b.capacity = b.design_capacity = 1.1
        b.charge = self.carga * 1.1
        b.cell_voltage = [b.voltage / 4] * 4
        b.present = True
        b.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO
        self.pub_bat.publish(b)

    def informe(self):
        izq, der, s = getattr(self, 'salida', (0, 0, self.succion))
        self.get_logger().info(f'[{self.modo}] motores izq {izq:+.2f} der {der:+.2f} | '
                               f'succión del {s["front"]:.0f} % '
                               f'tras {s["rear"]:.0f} % | batería {self.carga * 100:.0f} % '
                               f'({self.corriente:.1f} A)')


def main():
    rclpy.init()
    n = FirmwareSimulado()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    finally:
        n.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
