from setuptools import find_packages, setup

package_name = 'carro_trepador_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='juan',
    maintainer_email='juan_s.castano@uao.edu.co',
    description='Supervisor, cinemática diferencial, control de succión y estimador de postura '
                'del robot trepador',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'state_machine_node = carro_trepador_control.state_machine_node:main',
            'kinematics_node = carro_trepador_control.kinematics_node:main',
            'suction_control_node = carro_trepador_control.suction_control_node:main',
            'joint_state_estimator_node = carro_trepador_control.joint_state_estimator_node:main',
        ],
    },
)
