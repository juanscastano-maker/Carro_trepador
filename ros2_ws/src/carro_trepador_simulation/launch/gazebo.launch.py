"""
Simula el robot en Gazebo Fortress y lo conecta con ROS 2.

Tópicos disponibles en ROS 2:
  /imu/front/data, /imu/rear/data  IMUs simuladas (mismos tópicos que el firmware)
  /joint_states                    ángulos de las articulaciones (mientras no exista el estimador)
  /sim/cmd_vel                     tracción de las ruedas (la usa sim_bridge_node)
  /sim/odom                        odometría de la simulación
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('carro_trepador_description')
    with open(os.path.join(pkg, 'urdf', 'carro_trepador.urdf'), 'r') as f:
        robot_description = f.read()

    sim = get_package_share_directory('carro_trepador_simulation')
    world = os.path.join(sim, 'worlds', 'vacio.sdf')
    rviz = LaunchConfiguration('rviz')
    gui = LaunchConfiguration('gui')
    # -r: arranca la simulación corriendo; -s: solo el servidor, sin ventana
    gz_args = PythonExpression(
        ["'-r ' + ('' if '", gui, "' == 'true' else '-s ') + '", world, "'"])

    return LaunchDescription([
        DeclareLaunchArgument('rviz', default_value='false',
                              description='Abrir también RViz2'),
        DeclareLaunchArgument('gui', default_value='true',
                              description='Abrir la ventana de Gazebo (false = sin ventana)'),

        # Para que Gazebo encuentre las mallas (package://carro_trepador_description/...)
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', os.path.dirname(pkg)),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(
                get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')),
            launch_arguments={'gz_args': gz_args}.items(),
        ),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
        ),

        # Crea el robot en Gazebo a partir de /robot_description
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=['-topic', 'robot_description', '-name', 'carro_trepador', '-z', '0.02'],
            output='screen',
        ),

        # Puente entre tópicos de Gazebo y de ROS 2
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            arguments=[
                '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
                '/joint_states@sensor_msgs/msg/JointState[ignition.msgs.Model',
                '/imu/front/data@sensor_msgs/msg/Imu[ignition.msgs.IMU',
                '/imu/rear/data@sensor_msgs/msg/Imu[ignition.msgs.IMU',
                '/sim/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
                '/sim/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
            ],
            output='screen',
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', os.path.join(pkg, 'rviz', 'display.rviz')],
            parameters=[{'use_sim_time': True}],
            condition=IfCondition(rviz),
        ),
    ])
