"""
Prueba de integración del supervisor (state_machine_node).

A diferencia de las pruebas unitarias, aquí corre el nodo de verdad con ROS 2: un nodo de
prueba le publica IMUs y órdenes, y se revisa lo que el supervisor publica.
"""

import math
import time

import pytest
import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, Float32

from carro_trepador_control.state_machine_node import StateMachineNode


class Robot:
    """Hace de GUI y de firmware a la vez para hablar con el supervisor."""

    def __init__(self):
        rclpy.init()
        self.supervisor = StateMachineNode()
        self.nodo = rclpy.create_node('robot_de_prueba')
        self.ejecutor = SingleThreadedExecutor()
        self.ejecutor.add_node(self.supervisor)
        self.ejecutor.add_node(self.nodo)
        self.pub_cmd = self.nodo.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_e_stop = self.nodo.create_publisher(
            Bool, '/e_stop', QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE))
        self.pub_imu = {m: self.nodo.create_publisher(Imu, f'/imu/{m}/data', 10)
                        for m in ('front', 'rear')}
        self.safe = None
        self.override = None
        self.nodo.create_subscription(Twist, '/cmd_vel_safe',
                                      lambda m: setattr(self, 'safe', m), 10)
        self.nodo.create_subscription(Float32, '/suction_override',
                                      lambda m: setattr(self, 'override', m.data), 10)
        self.inclinacion = 0.0
        self.velocidad = 0.0

    def correr(self, segundos):
        """Publica IMUs y la orden actual como lo harían la GUI y el firmware."""
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            cmd = Twist()
            cmd.linear.x = self.velocidad
            self.pub_cmd.publish(cmd)
            for pub in self.pub_imu.values():
                imu = Imu()
                imu.orientation_covariance[0] = -1.0  # solo acelerómetro
                t = math.radians(self.inclinacion)
                imu.linear_acceleration.x = 9.8 * math.sin(t)
                imu.linear_acceleration.z = 9.8 * math.cos(t)
                pub.publish(imu)
            self.ejecutor.spin_once(timeout_sec=0.02)

    def cerrar(self):
        self.supervisor.destroy_node()
        self.nodo.destroy_node()
        rclpy.shutdown()


@pytest.fixture
def robot():
    r = Robot()
    yield r
    r.cerrar()


def test_limita_la_velocidad(robot):
    robot.velocidad = 0.5  # más que el máximo (0.25)
    robot.correr(1.5)
    assert robot.safe.linear.x == pytest.approx(0.25)


def test_parada_detiene_y_liberar_exige_soltar_los_controles(robot):
    robot.velocidad = 0.1
    robot.correr(1.0)
    assert robot.safe.linear.x == pytest.approx(0.1)

    robot.pub_e_stop.publish(Bool(data=True))
    robot.correr(0.5)
    assert robot.safe.linear.x == 0.0

    robot.pub_e_stop.publish(Bool(data=False))  # liberada con el control todavía en 0.1
    robot.correr(0.5)
    assert robot.safe.linear.x == 0.0, ('no debe arrancar hasta que el operador suelte '
                                        'los controles')

    robot.velocidad = 0.0
    robot.correr(0.3)
    robot.velocidad = 0.1
    robot.correr(0.5)
    assert robot.safe.linear.x == pytest.approx(0.1)


def test_en_la_pared_garantiza_succion_minima(robot):
    robot.inclinacion = 90.0
    robot.correr(1.0)
    assert robot.supervisor.estado == 'PARED'
    assert robot.override >= 60.0


def test_sin_ordenes_de_la_gui_se_detiene(robot):
    robot.velocidad = 0.1
    robot.correr(1.0)
    robot.pub_cmd = robot.nodo.create_publisher(Twist, '/otro_topico', 10)  # la GUI "se cae"
    robot.correr(1.0)
    assert robot.safe.linear.x == 0.0
