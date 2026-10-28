"""
Cinemática diferencial del robot trepador (kinematics_node).

Convierte la velocidad validada por el supervisor (/cmd_vel_safe: lineal en m/s y angular en
rad/s) en la velocidad de cada lado (/cmd_motors: [izquierda, derecha], de -1 a 1, donde 1 es la
velocidad máxima de los N20). Es el único publicador de /cmd_motors.

Si una rueda pediría más de su máximo, se escalan las dos por igual: así se conserva la
curvatura de la trayectoria en vez de recortar solo un lado.
"""

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray


def velocidades_rueda(v, w, separacion, v_max):
    """Devuelve (izquierda, derecha) normalizadas a [-1, 1]."""
    izq = (v - w * separacion / 2.0) / v_max
    der = (v + w * separacion / 2.0) / v_max
    mayor = max(abs(izq), abs(der))
    if mayor > 1.0:
        izq /= mayor
        der /= mayor
    return izq, der


class KinematicsNode(Node):
    """Convierte /cmd_vel_safe en /cmd_motors."""

    def __init__(self):
        super().__init__('kinematics_node')
        # Distancia entre los centros de las llantas (URDF) y velocidad máxima de rueda:
        # N20 de 300 RPM a 6 V; alimentados con 5 V (BEC) dan unos 250 RPM.
        # Con llanta de 15 mm de radio: 250/60 * 2π * 0.015 ≈ 0.39 m/s
        self.separacion = self.declare_parameter('separacion_ruedas', 0.1658).value
        self.v_max = self.declare_parameter('velocidad_max_rueda', 0.39).value

        self.pub = self.create_publisher(Float32MultiArray, '/cmd_motors', 10)
        self.create_subscription(Twist, '/cmd_vel_safe', self.al_recibir, 10)
        self.get_logger().info(
            f'kinematics_node listo (separación {self.separacion} m, '
            f'velocidad máxima de rueda {self.v_max} m/s)')

    def al_recibir(self, msg):
        izq, der = velocidades_rueda(msg.linear.x, msg.angular.z, self.separacion, self.v_max)
        self.pub.publish(Float32MultiArray(data=[float(izq), float(der)]))


def main(args=None):
    rclpy.init(args=args)
    node = KinematicsNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
