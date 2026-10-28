## Vehículo Robótico de Inspección Teleoperado con Adherencia por Succión Aerodinámica

Este repositorio contiene la arquitectura de software, la descripción URDF, el firmware micro-ROS y los modelos matemáticos de un robot trepador articulado. El robot tiene dos módulos unidos por una articulación central **pasiva** y se adhiere a superficies verticales con la succión de dos turbinas BLDC, una por módulo. Cada módulo tiene una IMU MPU6050 para medir su inclinación. Una ESP32-S3 controla motores y turbinas y se comunica por Wi-Fi con ROS 2 Humble en el PC mediante micro-ROS.

---

## 📸 Vista Previa

*(no tenemos aun)*

---

## 🧭 Arquitectura

La arquitectura completa (nodos, tópicos, servicios, seguridad, notificaciones y simulación) está en
[`docs/arquitectura/Arquitectura_Carro_trepador_v5.docx`](docs/arquitectura/Arquitectura_Carro_trepador_v5.docx).

**Robot real**

![Grafo de nodos del robot real](docs/arquitectura/grafo%20nodos%20microproyecto.drawio.png)

**Simulación (Gazebo)**

![Grafo de nodos de la simulación](docs/arquitectura/grafo%20nodos%20simulacion%20microproyecto.drawio.png)

Los dos `.drawio.png` llevan el diagrama editable incluido: se abren directamente en [app.diagrams.net](https://app.diagrams.net).

Ideas principales:

- El operador usa una GUI PyQt (`custom_gui_node`) que **no** manda órdenes directas a los motores: envía peticiones al supervisor (`state_machine_node`), que las valida según el estado del robot (suelo, pared, prueba, parada).
- **El operador decide todas las paradas.** La GUI activa y libera la parada (`/e_stop`) directo en el firmware; el supervisor la escucha pero nunca la activa, para que una falla de un nodo o un sensor no detenga el robot sin motivo.
- El supervisor **notifica todo** lo que el robot hace y le pasa (`/gui/notifications`), incluido el nivel de batería, que la GUI muestra como el indicador de un celular.
- El firmware tiene un watchdog: si deja de recibir `/heartbeat` por 500 ms (se perdió el control), deja el robot quieto y con la succión al máximo.
- En simulación, Gazebo y `sim_bridge_node` reemplazan al firmware; los demás nodos son los mismos que en el robot real.
- El video de la cámara OV2640 no pasa por ROS 2: la ESP32 lo sirve por HTTP MJPEG desde su otro núcleo, para no competir con los comandos.

---

## 📁 Estructura del Repositorio

```text
Carro_trepador/
├── README.md
├── .gitignore
├── Carro_trepador.code-workspace
│
├── ros2_ws/                          # Workspace de ROS 2: software que corre en el PC
│   └── src/
│       ├── carro_trepador_bringup/       # Launch para arrancar todo el sistema
│       ├── carro_trepador_control/       # Supervisor, cinemática, succión y estimador de postura
│       ├── carro_trepador_description/   # Modelo URDF del robot
│       ├── carro_trepador_interfaces/    # Mensaje propio Notificacion.msg
│       └── carro_trepador_teleop/        # GUI de teleoperación
│
├── firmware/                         # Proyecto PlatformIO / micro-ROS para la ESP32-S3
│   ├── platformio.ini
│   ├── include/pines.h               # Mapa de pines
│   ├── lib/                          # Drivers (IMU, INA226, DRV8833, ESC, rampa, filtro)
│   └── src/                          # main.cpp (robot), robot/ (video) y pruebas/ (hardware)
│
├── hardware/                         # Diseños CAD (STEP/STL) y diagramas eléctricos
│
├── matlab/                           # Modelos matemáticos, cinemática y pruebas de succión
│   ├── cinematica/
│   ├── control/
│   ├── dinamica/
│   └── simulaciones/
│
├── scripts/                          # Herramientas auxiliares fuera de ROS 2
│
└── docs/                             # Documentación técnica
    ├── Anteproyecto_VehiculoTrepador.pdf
    ├── Lista de materiales a comprar.pdf
    ├── arquitectura/                 # Arquitectura v5 y grafos (robot real y simulación)
    ├── cinematica/
    ├── control/
    └── simulacion/
```

`ros2_ws/` contiene solo el software ROS 2 que corre en el PC y se compila con `colcon`. El firmware también forma parte del sistema ROS (se comunica por micro-ROS), pero corre en la ESP32 y se compila con PlatformIO, por eso está en su propia carpeta.

---

## ⚙️ Requisitos

- Ubuntu 22.04 con **ROS 2 Humble**.
- **micro-ROS agent** para Humble (ver abajo).
- **PlatformIO** (extensión de VS Code o `pio` en la terminal) para el firmware.
- Python 3 con PyQt5 (`sudo apt install python3-pyqt5`).
- Gazebo Fortress con el puente a ROS 2 (`sudo apt install ros-humble-ros-gz`), solo para simular.

### Instalar el micro-ROS agent

Opción con Docker:

```bash
docker run -it --rm --net=host microros/micro-ros-agent:humble udp4 --port 8888
```

Opción compilándolo en un workspace aparte (fuera de este repositorio):

```bash
mkdir -p ~/microros_ws/src && cd ~/microros_ws
git clone -b humble https://github.com/micro-ROS/micro_ros_setup.git src/micro_ros_setup
source /opt/ros/humble/setup.bash
rosdep update && rosdep install --from-paths src --ignore-src -y
colcon build && source install/local_setup.bash
ros2 run micro_ros_setup create_agent_ws.sh
ros2 run micro_ros_setup build_agent.sh
source install/local_setup.bash
```

---

## ▶️ Compilar y ejecutar

### ROS 2 (PC)

```bash
cd ~/Carro_trepador/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -y
colcon build --symlink-install
source install/setup.bash
```

Todo el sistema del PC, con el agente de micro-ROS incluido (el agente necesita su workspace
cargado: `source ~/microros_ws/install/setup.bash`, o agregarlo a `~/.bashrc`):

```bash
ros2 launch carro_trepador_bringup bringup.launch.py url_video:=http://<IP-del-robot>:81/stream
```

Sin el robot (la ESP32 la reemplaza un firmware simulado):

```bash
ros2 launch carro_trepador_bringup bringup.launch.py simulado:=true
ros2 param set /firmware_simulado inclinacion_delantera 90.0   # simular que sube a la pared
```

Otros argumentos: `rviz:=false`, `gui:=false`, `agente:=false`. Los parámetros de todos los nodos
están en `carro_trepador_bringup/config/parametros.yaml`.

### Firmware (ESP32-S3)

Antes de compilar, copiar `firmware/include/credenciales_wifi.ejemplo.h` como
`credenciales_wifi.h` y poner la red Wi-Fi y la IP del PC (`hostname -I`).

```bash
cd ~/Carro_trepador/firmware
pio run -e esp32s3_cam                  # compilar
pio run -e esp32s3_cam -t upload        # cargar a la placa
pio device monitor                      # ver el puerto serie (muestra la IP y la dirección del video)
```

---

## 🤖 ROS 2

La carpeta `ros2_ws/` contiene el **workspace de ROS 2** del proyecto. Dentro de `ros2_ws/src/` están los 5 paquetes del sistema:

### `carro_trepador_bringup`

Arranque del sistema en el PC:

- `bringup.launch.py`: lanza el agente de micro-ROS, los cuatro nodos de control, `robot_state_publisher`, RViz2 y la GUI. Con `simulado:=true` cambia el agente por el firmware simulado.
- `config/parametros.yaml`: parámetros de todos los nodos.
- `rviz/robot.rviz`: RViz2 con el marco fijo `odom`, para ver la inclinación del robot.
- `firmware_simulado`: herramienta de prueba que hace de ESP32 en el PC (no es parte de la arquitectura).

### `carro_trepador_control`

Contiene los cuatro nodos que toman decisiones y hacen los cálculos:

- **`state_machine_node` (supervisor de seguridad):** decide el estado del robot (suelo, transición, pared), limita la velocidad y la succión según el estado y el modo prueba, publica el `/heartbeat` del watchdog y notifica todo a la GUI (`/gui/notifications`). La parada de emergencia la decide solo el operador.
- **`kinematics_node`:** cinemática diferencial. Convierte la velocidad validada (`/cmd_vel_safe`) en la velocidad de las ruedas izquierda y derecha (`/cmd_motors`).
- **`suction_control_node`:** calcula la potencia de cada turbina BLDC a partir de la inclinación de su IMU. `/suction_override` del supervisor solo puede subirla.
- **`joint_state_estimator_node`:** estima el ángulo de la articulación central con las dos IMUs y publica `/joint_states` y `/tf` para ver el robot en RViz2.

### `carro_trepador_description`

Modelo del robot para RViz2 y Gazebo Fortress, adaptado de la exportación de SolidWorks:

- `urdf/carro_trepador.urdf`: dos módulos unidos por la articulación central pasiva (`chasis_trasero_joint`), 6 ruedas (4 con motor N20 y 2 traseras libres), las hélices de las turbinas y los marcos de las dos IMUs.
- `meshes/`: mallas visuales reducidas; las colisiones usan cajas y cilindros.
- `launch/display.launch.py`: muestra el modelo en RViz2 con deslizadores para mover las articulaciones.
- `launch/gazebo.launch.py`: simula el robot en Gazebo Fortress. Las IMUs simuladas publican en `/imu/front/data` y `/imu/rear/data`, como el firmware, y `/sim/cmd_vel` permite probar la tracción.
- `worlds/vacio.sdf`: mundo vacío con suelo.

```bash
ros2 launch carro_trepador_description display.launch.py      # RViz2
ros2 launch carro_trepador_description gazebo.launch.py       # Gazebo (rviz:=true abre también RViz2; gui:=false, sin ventana)
```

Las masas e inercias vienen de SolidWorks y aún no se han comparado con el peso real del robot.

> **Nota sobre el giro:** con 6 ruedas en fila y las traseras sin motor, la fricción lateral de las llantas frena el giro en el sitio. En Gazebo, con la misma fricción en todas las direcciones, el robot avanza pero **no gira**. Por eso las llantas simuladas tienen fricción lateral baja (`mu1 = 0.3` en la dirección del eje y `mu2 = 1.0` al rodar); con 0.5 o más ya casi no gira. Hay que comprobar en el robot real si gira bien sobre las superficies de prueba.

### `carro_trepador_interfaces`

Mensajes propios: `Notificacion.msg` (nivel INFO/AVISO/ALERTA, origen, código y texto), que el supervisor envía a la GUI. Lo demás usa tipos estándar de ROS 2.

### `carro_trepador_teleop`

Contiene `custom_gui_node`, la interfaz gráfica PyQt del operador:

- Movimiento con W A S D, flechas o botones (`/cmd_vel`) y petición de succión al supervisor.
- Parada de emergencia (botón o Espacio), que publica `/e_stop` directo al firmware; se libera solo con los controles sueltos.
- Modo prueba (servicio `/set_test_mode`).
- Estado del robot, batería tipo celular, notificaciones con filtro y video de la cámara.

---

## 🛠️ Hardware

La carpeta `hardware/` resguarda los recursos físicos de construcción:

- Modelos CAD exportados en formatos STEP y STL para manufactura en Foam Board e impresión 3D.
- Diagramas de conexiones eléctricas entre la ESP32-S3, sensores, drivers de potencia y turbinas.

Componentes principales (ver `docs/Lista de materiales a comprar.pdf`):

- ESP32-S3 CAM N16R8 con cámara OV2640.
- 4 motores N20 con driver DRV8833 para la tracción.
- 2 motores BLDC iFlight XING2 1404 con ESC Hobbywing de 30 A para las turbinas.
- 2 IMU MPU6050.
- Batería LiPo 4S HV de 1100 mAh.

---

## ⚡ Firmware (ESP32-S3)

La carpeta `firmware/` contiene el proyecto de PlatformIO/C++ que corre en la placa:

- **Núcleo 1, `micro_ros_esp32_node` (`src/main.cpp`):** conexión micro-ROS por Wi-Fi/UDP con el agente en el PC (se reconecta solo si el agente se cae). Lee las dos IMU MPU6050 por I2C con un filtro de Mahony, mide la batería con el INA226, genera el PWM de los motores N20 y de los ESC con rampas, y ejecuta el watchdog y el modo seguro.
- **Seguridad:** sin heartbeat por 500 ms o con la parada activa, la tracción se detiene y las turbinas van al máximo si el robot no está en el suelo (en el suelo se apagan). Al encender, nada se mueve hasta el primer heartbeat. El LED de la placa muestra el estado: naranja sin agente, azul esperando al supervisor, verde normal y rojo en parada o modo seguro.
- **Núcleo 0, servidor de video:** transmite la cámara OV2640 por HTTP MJPEG en el puerto 81.

**Pruebas de hardware:** `firmware/src/pruebas/` tiene un programa por subsistema (cámara, IMUs, motores, INA226 y ESC), cada uno en su propio entorno de PlatformIO. El mapa de pines está en `firmware/include/pines.h`, y las conexiones, la alimentación y las precauciones, en [`docs/electronica/Conexiones_Carro_trepador_v3.docx`](docs/electronica/Conexiones_Carro_trepador_v3.docx).

```bash
cd firmware
pio run -e prueba_imus -t upload && pio device monitor   # o prueba_camara, prueba_motores, prueba_potencia, prueba_esc
```

---

## 🧮 MATLAB

La carpeta `matlab/` está destinada al desarrollo y análisis matemático realizado en MATLAB.

Se utilizará principalmente para:

- Desarrollo y validación de modelos matemáticos.
- Cinemática.
- Dinámica.
- Diseño y análisis de controladores.
- Simulaciones.
- Análisis de estabilidad.
- Validación de algoritmos antes de su implementación en ROS 2.

Los desarrollos de MATLAB que posteriormente se implementen como nodos o componentes del sistema servirán como referencia para su implementación final.

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

Scripts disponibles:

- `adaptar_urdf_solidworks.py`: convierte la exportación de SolidWorks (sw_urdf_exporter, formato ROS 1) en el URDF de ROS 2 de `carro_trepador_description` y copia las mallas. Usarlo cada vez que se reexporte el ensamble:

  ```bash
  python3 scripts/adaptar_urdf_solidworks.py --exportacion <carpeta exportada>
  ```

---

## 🧪 Tests

Las pruebas están dentro de cada paquete (carpeta `test/`) y se corren con:

```bash
cd ~/Carro_trepador/ros2_ws
colcon build && source install/setup.bash
colcon test && colcon test-result --verbose
```

- **Unitarias** (`carro_trepador_control/test/`): cinemática, succión automática, cálculos de las IMUs y del estimador.
- **Integración** (`test_supervisor.py`): corre el supervisor real y revisa lo que publica (límite de velocidad, parada y liberación, succión en la pared, GUI caída).
- **Estilo** (`test_flake8.py`, `test_pep257.py`): revisan el formato del código según las reglas de ROS 2.

Pruebas de un solo archivo, más rápido: `python3 -m pytest src/carro_trepador_control/test/test_succion.py -v`.

Las pruebas de hardware están en `firmware/src/pruebas/` (ver la sección de firmware).

---

## 📚 Documentación

La carpeta `docs/` contiene la documentación técnica del proyecto, organizada por áreas:

```text
docs/
├── arquitectura/
├── cinematica/
├── control/
└── simulacion/
```

Aquí se almacenan:

- Decisiones de arquitectura.
- Diagramas.
- Documentación de interfaces.
- Procedimientos técnicos.
- Resultados de pruebas.
- Notas de implementación.
- Información necesaria para facilitar la incorporación de nuevos integrantes.

La documentación general del proyecto y las instrucciones principales de uso deberán mantenerse actualizadas en este repositorio.
