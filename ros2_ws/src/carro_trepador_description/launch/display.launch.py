"""Muestra el modelo del robot en RViz2, con deslizadores para mover las articulaciones."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('carro_trepador_description')
    with open(os.path.join(pkg, 'urdf', 'carro_trepador.urdf'), 'r') as f:
        robot_description = f.read()

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
        ),
        # Ventana con un deslizador por articulación (ruedas, hélices y articulación central)
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', os.path.join(pkg, 'rviz', 'display.rviz')],
        ),
    ])
