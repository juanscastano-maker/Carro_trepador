## Vehículo Robótico de Inspección Teleoperado con Adherencia por Succión Aerodinámica

Este repositorio contiene la arquitectura de software, modelos de simulación, descripción URDF y firmware de micro-ROS para el desarrollo de un robot trepador articulado. El sistema utiliza fuerza de succión mediante turbinas BLDC para adherirse a superficies verticales, combinado con sensores de inclinación (IMU) y control en tiempo real mediante un microcontrolador ESP32-S3 enlazado a ROS 2.

---

## 📸 Vista Previa

*(no tenemos aun)*  

---


## 📁 Estructura del Repositorio

```text
Carro_trepador/
├── README.md
├── .gitignore
├── Carro_trepador.code-workspace
│
├── ros2_ws/                     # Workspace principal de ROS 2
│   └── src/                     # Código fuente de los paquetes
│       ├── carro_trepador_description/
│       ├── carro_trepador_interfaces/
│       ├── carro_trepador_control/
│        └── carro_trepador_teleop/
│ 
├── hardware/                    # Diseños CAD (STEP/STL) del chasis y lista de materiales (BOM)
│ 
├── firmware/                    # Código PlatformIO / micro-ROS para la ESP32-S3
│
├── matlab/                      # Modelos matemáticos, cinemática y pruebas de succión
│   ├── cinematica/
│   ├── control/
│   ├── dinamica/
│   └── simulaciones/
│
├── scripts/                     # Scripts de Bash para automatización y configuración
│ 
├── tests/                       # Pruebas de integración global fuera de ROS 2
│
└── docs/                        # Diagramas eléctricos, reportes técnicos y arquitectura
    ├── arquitectura/
    ├── cinematica/
    ├── control/
    └── simulacion/
```

---

## 🤖 ROS 2

La carpeta `ros2_ws/` contiene el **Workspace de ROS 2** del proyecto. Dentro de `ros2_ws/src/` se alojan los 4 paquetes modulares del sistema:

### `carro_trepador_description`

Almacena la geometría, simulación visual y físicas del robot:

- Modelos URDF/Xacro del robot articulado de 2 módulos.
- Links, joints y parámetros de inercia/masa del chasis en Foam Board.
- Mallas 3D (`.stl`).
- Configuración para RViz2 y entornos de **Gazebo**.
- Mundos de simulación (superficies planas, paredes verticales y obstáculos).
- Plugins de sensores (IMU MPU6050 virtual) y física en Gazebo.
- Archivos de lanzamiento (`.launch.py`) para visualización y simulación.

### `carro_trepador_interfaces`

Define la estructura de datos para la comunicación distribuida (especialmente útil para micro-ROS con la ESP32-S3):

- Messages (`.msg`) personalizados: lecturas de acelerómetro/giroscopio, estado de las turbinas BLDC y telemetría.
- Services (`.srv`): comandos de calibración de sensores o activación/desactivación manual de succión.
- Actions (`.action`): secuencias complejas como transiciones automáticas de pared a piso.

### `carro_trepador_control`

Contiene la inteligencia algorítmica y el procesamiento matemático del robot:

- **Cinemática directa e inversa:** Cálculo de posición relativa y control del ángulo de la articulación central.
- **Control de adherencia:** Ajuste dinámico de potencia en las turbinas BLDC según el ángulo de inclinación detectado por la IMU.
- **Coordinación de motores:** Control de velocidad y sincronización de los motores N20 de tracción.
- Algoritmos de control (PID/MPC) e integración con la IMU MPU6050.
- Pruebas de locomoción, estabilidad y algoritmos de control en simulación.

### `carro_trepador_teleop`

Gestiona el mando a distancia e interacción con el operador:

- Mapeo de mandos Gamepad / Joystick o comandos por teclado.
- Publicación de velocidades en el tópico `/cmd_vel`.
- Parada de emergencia por software y selección de modos (Manual / Auto-adherencia).
- Visualización gráfica del estado del sistema en tiempo real.

---

## 🛠️ Hardware

La carpeta `hardware/` resguarda los recursos físicos de construcción:

- Modelos CAD exportados en formatos STEP y STL para manufactura en Foam Board e impresión 3D.
- Diagramas de conexiones eléctricas entre la ESP32-S3, sensores, drivers de potencia y turbinas.
- Lista de Materiales (BOM) con especificaciones de componentes y peso total estimado.

---

## ⚡ Firmware (ESP32-S3)

La carpeta `firmware/` contiene el proyecto de PlatformIO/C++ ejecutado directamente en la placa microcontroladora:

- Nodo **micro-ROS** para conexión mediante agente serial/Wi-Fi con el espacio de trabajo de ROS 2.
- Lectura en tiempo real de los sensores IMU MPU6050 mediante bus I2C.
- Generación de señales PWM para el control de los ESC de las turbinas BLDC y drivers de motores N20.

---

## 🧮 MATLAB

La carpeta `matlab/` estará destinada al desarrollo y análisis matemático realizado en MATLAB.

Se utilizará principalmente para:

- Desarrollo y validación de modelos matemáticos.
- Cinemática.
- Dinámica.
- Diseño y análisis de controladores.
- Simulaciones.
- Análisis de estabilidad.
- Validación de algoritmos antes de su implementación en ROS 2.

Los desarrollos de MATLAB que posteriormente sean implementados como nodos o componentes del sistema podrán utilizarse como referencia para su implementación final.

---

## 🧰 Scripts

La carpeta `scripts/` contendrá herramientas auxiliares que no correspondan directamente a un paquete ROS 2.

Puede incluir:

- Scripts de Python.
- Scripts Bash.
- Herramientas de automatización.
- Procesamiento de datos.
- Conversión de archivos.
- Herramientas de configuración o diagnóstico.

Los scripts que formen parte directamente de un paquete ROS 2 deberán permanecer dentro del paquete correspondiente.

---

## 🧪 Tests

La carpeta `tests/` estará destinada a pruebas generales del proyecto.

Se podrán incluir:

- Pruebas unitarias.
- Pruebas de algoritmos.
- Pruebas de comunicación.
- Pruebas de integración.
- Validación de componentes.
- Resultados y herramientas de verificación.

Las pruebas específicas de un paquete ROS 2 podrán mantenerse dentro del propio paquete.

---

## 📚 Documentación

La carpeta `docs/` contendrá documentación técnica relacionada con el desarrollo del software.

Se organizará por áreas, por ejemplo:

```text
docs/
├── arquitectura/
├── cinematica/
├── control/
└── simulacion/
```

Aquí podrán almacenarse:

- Decisiones de arquitectura.
- Diagramas.
- Documentación de interfaces.
- Procedimientos técnicos.
- Resultados de pruebas.
- Notas de implementación.
- Información necesaria para facilitar la incorporación de nuevos integrantes.

La documentación general del proyecto y las instrucciones principales de uso deberán mantenerse actualizadas en este repositorio.






