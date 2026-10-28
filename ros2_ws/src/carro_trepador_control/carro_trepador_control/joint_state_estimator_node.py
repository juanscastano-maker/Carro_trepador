"""
Estimador de la postura del robot trepador (joint_state_estimator_node).

Ver docs/arquitectura/Arquitectura_Carro_trepador_v5.docx. Solo recibe las dos IMUs y publica:

  /joint_states  las 9 articulaciones móviles del URDF. La articulación central
                 (chasis_trasero_joint, pasiva y sin sensor) se estima como
                     ángulo = cabeceo delantero - cabeceo trasero
                 Las ruedas y las hélices no tienen encoder: se publican en 0 para que
                 robot_state_publisher pueda armar el árbol completo.
  /tf            marco_fijo -> base_link con la inclinación del módulo trasero (alabeo y
                 cabeceo). Sin posición ni rumbo: el MPU6050 no tiene magnetómetro ni hay
                 odometría, así que el robot se dibuja quieto en el origen pero inclinado como
                 el real.

En el URDF el eje de chasis_trasero_joint queda en -y del módulo trasero: ángulo positivo =
módulo delantero con la nariz hacia arriba respecto al trasero (paso de suelo a pared).
"""

import math
import time

from geometry_msgs.msg import TransformStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, JointState
from tf2_ros import TransformBroadcaster

from carro_trepador_control.control.imu import alabeo, cabeceo

ARTICULACION_CENTRAL = 'chasis_trasero_joint'
SIN_SENSOR = ['rueda_trasera_derecha_joint', 'rueda_trasera_izquierda_joint',
              'rueda_media_derecha_joint', 'rueda_media_izquierda_joint',
              'rueda_delantera_derecha_joint', 'rueda_delantera_izquierda_joint',
              'helice_trasera_joint', 'helice_delantera_joint']
LIMITE = math.radians(90.0)  # límite de chasis_trasero_joint en el URDF


def cuaternion_rpy(roll, pitch, yaw):
    """(x, y, z, w) a partir de alabeo, cabeceo y rumbo en radianes (convención de ROS)."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy)


class JointStateEstimatorNode(Node):
    """Publica /joint_states y /tf a partir de las dos IMUs."""

    def __init__(self):
        super().__init__('joint_state_estimator_node')
        self.marco_fijo = self.declare_parameter('marco_fijo', 'odom').value
        self.alfa = self.declare_parameter('filtro', 0.2).value  # 1 = sin filtro
        self.timeout_imu = self.declare_parameter('timeout_imu', 0.2).value
        self.ultimo = {'front': None, 'rear': None}
        self.t_imu = {'front': None, 'rear': None}
        self.angulo = 0.0

        self.pub = self.create_publisher(JointState, '/joint_states', 10)
        self.tf = TransformBroadcaster(self)
        for m in ('front', 'rear'):
            self.create_subscription(Imu, f'/imu/{m}/data', lambda msg, m=m: self.al_imu(m, msg),
                                     qos_profile_sensor_data)
        self.create_timer(1.0 / self.declare_parameter('frecuencia', 30.0).value, self.publicar)
        self.get_logger().info(f'joint_state_estimator_node listo (marco fijo: {self.marco_fijo})')

    def al_imu(self, modulo, msg):
        self.ultimo[modulo] = msg
        self.t_imu[modulo] = time.monotonic()

    def vigente(self, modulo):
        t = self.t_imu[modulo]
        return t is not None and time.monotonic() - t < self.timeout_imu

    def publicar(self):
        delantera, trasera = self.vigente('front'), self.vigente('rear')
        # Sin alguna de las dos IMUs se conserva el último ángulo conocido
        if delantera and trasera:
            medido = math.radians(cabeceo(self.ultimo['front']) - cabeceo(self.ultimo['rear']))
            medido = max(-LIMITE, min(LIMITE, medido))
            self.angulo += self.alfa * (medido - self.angulo)

        ahora = self.get_clock().now().to_msg()
        js = JointState()
        js.header.stamp = ahora
        js.name = [ARTICULACION_CENTRAL] + SIN_SENSOR
        js.position = [self.angulo] + [0.0] * len(SIN_SENSOR)
        self.pub.publish(js)

        t = TransformStamped()
        t.header.stamp = ahora
        t.header.frame_id = self.marco_fijo
        t.child_frame_id = 'base_link'
        if trasera:
            # cabeceo() es positivo con la nariz arriba; en ROS eso es pitch negativo
            q = cuaternion_rpy(math.radians(alabeo(self.ultimo['rear'])),
                               -math.radians(cabeceo(self.ultimo['rear'])), 0.0)
            (t.transform.rotation.x, t.transform.rotation.y,
             t.transform.rotation.z, t.transform.rotation.w) = q
        else:
            t.transform.rotation.w = 1.0
        self.tf.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = JointStateEstimatorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
