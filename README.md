**Vehículo Robótico de Inspección Teleoperado con Adherencia por Succión Aerodinámica**

Este repositorio contiene la arquitectura de software, modelos de simulación, descripción URDF y firmware de micro-ROS para el desarrollo de un robot trepador articulado. El sistema utiliza fuerza de succión mediante turbinas BLDC para adherirse a superficies verticales, combinado con sensores de inclinación (IMU) y control en tiempo real mediante un microcontrolador ESP32-S3 enlazado a ROS 2.

---

## 📸 Vista Previa

*(no tenemos aun)*  

---


## 📁 Estructura del Repositorio

```text
Carro_trepador/
├── README.md
├── docs/                      # Diagramas eléctricos, esquemas y recursos de documentación
├── hardware/                  # Archivos CAD (STEP/STL) y Lista de Materiales (BOM)
├── firmware/                  # Código de micro-ROS / PlatformIO para la ESP32-S3
└── ros2_ws/                   # Workspace de ROS 2
    └── src/
        └── carro_trepador_description/
            ├── config/        # Configuraciones de RViz y controladores
            ├── launch/        # Archivos de lanzamiento (.launch.py)
            ├── meshes/        # Archivos 3D para visualización (.stl)
            └── urdf/          # Modelo del robot en formato Xacro/URDF
