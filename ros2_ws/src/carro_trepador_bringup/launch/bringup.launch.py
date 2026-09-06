import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Rutas a archivos de descripción (URDF)
    description_pkg = get_package_share_directory('carro_trepador_description')
    urdf_file = os.path.join(description_pkg, 'urdf', 'robot.urdf')

    with open(urdf_file, 'r') as infp:
        robot_description_config = infp.read()

    # 2. Definición de Nodos
    
    # Publicador de modelo 3D y transformaciones (TF)
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description_config}]
    )

    # Máquina de estados (Supervisor de seguridad)
    state_machine_node = Node(
        package='carro_trepador_control',
        executable='state_machine_node',
        output='screen'
    )

    # Control matemático de succión
    suction_control_node = Node(
        package='carro_trepador_control',
        executable='suction_control_node',
        output='screen'
    )

    # Cinemática diferencial de tracción
    kinematics_node = Node(
        package='carro_trepador_control',
        executable='kinematics_node',
        output='screen'
    )

    # Interfaz gráfica de usuario (PyQt)
    gui_node = Node(
        package='carro_trepador_teleop',
        executable='custom_gui_node',
        output='screen'
    )

    # 3. Retornar la lista de nodos a ejecutar
    return LaunchDescription([
        robot_state_publisher_node,
        state_machine_node,
        suction_control_node,
        kinematics_node,
        gui_node,
    ])
