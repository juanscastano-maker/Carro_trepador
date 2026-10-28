"""
Arranca todo el sistema del robot trepador en el PC.

(docs/arquitectura/Arquitectura_Carro_trepador_v5.docx)

  ros2 launch carro_trepador_bringup bringup.launch.py                       robot real
  ros2 launch carro_trepador_bringup bringup.launch.py simulado:=true        sin robot
                                                                             (firmware simulado)
  ros2 launch carro_trepador_bringup bringup.launch.py url_video:=http://192.168.1.50:81/stream

Argumentos:
  simulado   true: corre firmware_simulado en lugar del agente de micro-ROS
             (para probar sin el robot)
  agente     true: corre el agente de micro-ROS (UDP, puerto 8888) para hablar con la ESP32
  rviz       true: abre RViz2 con el modelo del robot moviéndose como el real
  gui        true: abre la interfaz del operador
  url_video  dirección del video de la ESP32 (la muestra el monitor serie al arrancar)

Los parámetros de los nodos están en config/parametros.yaml.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    bringup = get_package_share_directory('carro_trepador_bringup')
    descripcion = get_package_share_directory('carro_trepador_description')
    parametros = os.path.join(bringup, 'config', 'parametros.yaml')
    with open(os.path.join(descripcion, 'urdf', 'carro_trepador.urdf'), 'r') as f:
        urdf = f.read()

    simulado = LaunchConfiguration('simulado')
    usar_agente = PythonExpression(["'", LaunchConfiguration('agente'), "' == 'true' and '",
                                    simulado, "' != 'true'"])

    def nodo(paquete, ejecutable, **extra):
        return Node(package=paquete, executable=ejecutable, output='screen',
                    parameters=[parametros], **extra)

    return LaunchDescription([
        DeclareLaunchArgument('simulado', default_value='false'),
        DeclareLaunchArgument('agente', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('url_video', default_value=''),

        # Puente con la ESP32 (robot real) o firmware simulado (pruebas)
        ExecuteProcess(cmd=['ros2', 'run', 'micro_ros_agent', 'micro_ros_agent', 'udp4',
                            '--port', '8888'],
                       output='screen', condition=IfCondition(usar_agente)),
        Node(package='carro_trepador_bringup', executable='firmware_simulado', output='screen',
             condition=IfCondition(simulado)),

        # Control
        nodo('carro_trepador_control', 'state_machine_node'),
        nodo('carro_trepador_control', 'kinematics_node'),
        nodo('carro_trepador_control', 'suction_control_node'),
        nodo('carro_trepador_control', 'joint_state_estimator_node'),

        # Visualización
        Node(package='robot_state_publisher', executable='robot_state_publisher', output='screen',
             parameters=[{'robot_description': urdf}]),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', os.path.join(bringup, 'rviz', 'robot.rviz')],
             output='log', condition=IfCondition(LaunchConfiguration('rviz'))),

        # Operador
        Node(package='carro_trepador_teleop', executable='custom_gui_node', output='screen',
             parameters=[parametros, {'url_video': LaunchConfiguration('url_video')}],
             condition=IfCondition(LaunchConfiguration('gui'))),
    ])
