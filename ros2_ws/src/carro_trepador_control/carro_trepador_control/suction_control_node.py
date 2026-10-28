"""
Control de succión del robot trepador (suction_control_node).

Ver docs/arquitectura/Arquitectura_Carro_trepador_v5.docx. Calcula la potencia de cada turbina
(/cmd_suction/front y /cmd_suction/rear, de 0 a 100 %) a partir de la inclinación de su módulo:

  inclinación <= umbral_suelo  -> succion_suelo
  inclinación >= umbral_pared  -> succion_pared
  en medio                      -> interpolación lineal

/suction_override (del supervisor) tiene prioridad pero solo puede SUBIR la succión:
salida = max(automática, override). El supervisor manda ahí lo que pide el operador y la
succión mínima en la pared.

Rampa: la succión sube rápido (agarre) y baja despacio (evita soltarse de golpe y picos de
corriente en los ESC). Si la IMU de un módulo deja de llegar, ese módulo pasa a succion_pared:
ante la duda, mejor seguir pegado.
"""

import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32

from carro_trepador_control.control.imu import inclinacion

MODULOS = ('front', 'rear')


def succion_automatica(angulo, umbral_suelo, umbral_pared, succion_suelo, succion_pared):
    """Succión (0-100) según la inclinación del módulo en grados."""
    if angulo <= umbral_suelo:
        return succion_suelo
    if angulo >= umbral_pared:
        return succion_pared
    f = (angulo - umbral_suelo) / (umbral_pared - umbral_suelo)
    return succion_suelo + f * (succion_pared - succion_suelo)


class SuctionControlNode(Node):
    """Calcula la potencia de cada turbina a partir de la inclinación de su IMU."""

    def __init__(self):
        super().__init__('suction_control_node')
        p = self.declare_parameter
        self.umbral_suelo = p('umbral_suelo_grados', 25.0).value
        self.umbral_pared = p('umbral_pared_grados', 65.0).value
        self.succion_suelo = p('succion_suelo', 0.0).value
        self.succion_pared = p('succion_pared', 70.0).value
        self.subida = p('rampa_subida', 200.0).value   # %/s
        self.bajada = p('rampa_bajada', 25.0).value    # %/s
        self.timeout_imu = p('timeout_imu', 0.2).value
        self.periodo = 1.0 / p('frecuencia', 20.0).value

        self.angulo = {m: None for m in MODULOS}
        self.t_imu = {m: None for m in MODULOS}
        self.salida = {m: 0.0 for m in MODULOS}
        self.override = 0.0
        self.sin_imu = {m: False for m in MODULOS}

        self.pub = {m: self.create_publisher(Float32, f'/cmd_suction/{m}', 10) for m in MODULOS}
        for m in MODULOS:
            self.create_subscription(Imu, f'/imu/{m}/data', lambda msg, m=m: self.al_imu(m, msg),
                                     qos_profile_sensor_data)
        self.create_subscription(Float32, '/suction_override', self.al_override, 10)
        self.create_timer(self.periodo, self.ciclo)
        self.get_logger().info('suction_control_node listo')

    def al_imu(self, modulo, msg):
        angulo = inclinacion(msg)
        if angulo is not None:
            self.angulo[modulo] = angulo
            self.t_imu[modulo] = time.monotonic()

    def al_override(self, msg):
        self.override = max(0.0, min(100.0, msg.data))

    def ciclo(self):
        ahora = time.monotonic()
        for m in MODULOS:
            t = self.t_imu[m]
            sin_imu = t is None or ahora - t > self.timeout_imu
            if sin_imu != self.sin_imu[m]:
                self.sin_imu[m] = sin_imu
                if sin_imu:
                    self.get_logger().warn(
                        f'IMU {m} sin datos: turbina {m} a {self.succion_pared:.0f} %')
                else:
                    self.get_logger().info(f'IMU {m} de vuelta: succión automática')
            if sin_imu:
                automatica = self.succion_pared
            else:
                automatica = succion_automatica(self.angulo[m], self.umbral_suelo,
                                                self.umbral_pared, self.succion_suelo,
                                                self.succion_pared)
            objetivo = max(automatica, self.override)

            # Rampa
            actual = self.salida[m]
            if objetivo > actual:
                actual = min(objetivo, actual + self.subida * self.periodo)
            else:
                actual = max(objetivo, actual - self.bajada * self.periodo)
            self.salida[m] = actual
            self.pub[m].publish(Float32(data=float(actual)))


def main(args=None):
    rclpy.init(args=args)
    node = SuctionControlNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
