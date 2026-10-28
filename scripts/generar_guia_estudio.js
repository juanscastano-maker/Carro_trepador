// Genera docs/guias/Guia_de_estudio_software_Carro_trepador.docx
// Uso: npm install docx (una vez) y luego
//      node scripts/generar_guia_estudio.js docs/guias/Guia_de_estudio_software_Carro_trepador.docx
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  HeadingLevel, AlignmentType, LevelFormat, BorderStyle, PageBreak, TableOfContents, Footer,
  PageNumber, Header,
} = require('docx');

const AZUL = '2F5496', AZUL_CLARO = 'EBF3FB', TITULO = '1F4D78';
const ANCHO = 9638; // A4 con márgenes de 2 cm (11906 - 2*1134)

// ---------- ayudantes ----------
function runs(texto, base = {}) {
  // **negrita** y `código` dentro del texto
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean);
  return partes.map((p) => {
    if (p.startsWith('**')) return new TextRun({ ...base, text: p.slice(2, -2), bold: true });
    if (p.startsWith('`')) return new TextRun({ ...base, text: p.slice(1, -1), font: 'Consolas', size: 19, color: '7B2C2C' });
    return new TextRun({ ...base, text: p });
  });
}
const P = (t, o = {}) => new Paragraph({ children: runs(t), spacing: { after: 120 }, ...o });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H1b = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (t, nivel = 0) => new Paragraph({ numbering: { reference: 'vinetas', level: nivel }, children: runs(t), spacing: { after: 60 } });
const N = (t, ref = 'numeros') => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t), spacing: { after: 60 } });
const CASILLA = (t) => new Paragraph({ numbering: { reference: 'casillas', level: 0 }, children: runs(t), spacing: { after: 60 } });

function codigo(lineas) {
  return lineas.map((l, i) => new Paragraph({
    children: [new TextRun({ text: l || ' ', font: 'Consolas', size: 18 })],
    shading: { type: ShadingType.CLEAR, fill: 'F2F2F2', color: 'auto' },
    spacing: { before: i === 0 ? 60 : 0, after: i === lineas.length - 1 ? 160 : 0 },
    indent: { left: 200, right: 200 },
    keepNext: i < lineas.length - 1, keepLines: true,
  }));
}

function nota(titulo, texto) {
  return new Paragraph({
    children: [new TextRun({ text: titulo + ' ', bold: true, color: TITULO }), ...runs(texto)],
    shading: { type: ShadingType.CLEAR, fill: 'FFF4D6', color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: 'E3A008', space: 8 } },
    spacing: { before: 120, after: 160 },
    indent: { left: 200, right: 200 },
    keepLines: true,
  });
}

const borde = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
const bordes = { top: borde, bottom: borde, left: borde, right: borde };

function tabla(anchos, encabezado, filas) {
  const total = anchos.reduce((a, b) => a + b, 0);
  const celda = (texto, ancho, enc, par) => new TableCell({
    width: { size: ancho, type: WidthType.DXA },
    borders: bordes,
    shading: { type: ShadingType.CLEAR, fill: enc ? AZUL : (par ? AZUL_CLARO : 'FFFFFF'), color: 'auto' },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: enc ? [new TextRun({ text: texto, bold: true, color: 'FFFFFF' })] : runs(texto) })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: anchos,
    rows: [
      new TableRow({ tableHeader: true, children: encabezado.map((t, i) => celda(t, anchos[i], true)) }),
      ...filas.map((f, j) => new TableRow({ cantSplit: true, children: f.map((t, i) => celda(t, anchos[i], false, j % 2 === 0)) })),
    ],
  });
}
const espacio = () => new Paragraph({ children: [], spacing: { after: 80 } });

// ---------- contenido ----------
const c = [];

// Portada
c.push(new Paragraph({ children: [], spacing: { before: 2400 } }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Carro Trepador', size: 56, bold: true, color: TITULO })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: 'Guía de estudio del software', size: 36, color: '2E74B5' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Cómo está hecho el software del robot, cómo estudiarlo para entenderlo y cómo probarlo parte por parte', size: 24, italics: true })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 1600 }, children: [new TextRun({ text: 'Nodos de ROS 2 (PC) · Firmware de la ESP32-S3 · Pruebas', size: 22, color: '595959' })] }));
c.push(new Paragraph({ children: [new PageBreak()] }));

c.push(new Paragraph({ children: [new TextRun({ text: 'Contenido', bold: true, size: 32, color: TITULO })], spacing: { after: 200 } }));
c.push(new TableOfContents('Contenido', { hyperlink: true, headingStyleRange: '1-2' }));
c.push(P('Si el índice aparece vacío, en Word: clic derecho sobre él → Actualizar campos.', { children: [new TextRun({ text: 'Si el índice aparece vacío, en Word: clic derecho sobre él → Actualizar campos.', italics: true, color: '7F7F7F', size: 18 })] }));

// 1
c.push(H1('1. Para qué sirve esta guía'));
c.push(P('El software del Carro Trepador tiene dos partes que trabajan juntas: los **nodos de ROS 2**, que corren en el PC y toman las decisiones, y el **firmware**, que corre en la ESP32-S3 y mueve el hardware. En total son unas 2 900 líneas de código repartidas en una veintena de archivos.'));
c.push(P('Esta guía explica qué hace cada archivo, propone un **orden para estudiarlo** (de lo más simple a lo más complejo), deja **preguntas guía** con sus respuestas al final para comprobar que lo entendiste, y describe **cómo probar** cada parte, desde las pruebas automáticas hasta el robot en la pared.'));
c.push(P('El documento de referencia es **docs/arquitectura/Arquitectura_Carro_trepador_v5.docx** junto con el grafo **grafo nodos microproyecto.drawio.png**: todo el código es ese grafo convertido en programa.'));
c.push(nota('Estado actual:', 'todo el software compila y pasa sus pruebas en el PC, incluido el sistema completo con el firmware simulado. El firmware **no se ha probado todavía en la placa real**: esa prueba se hace siguiendo la sección 5.'));

// 2
c.push(H1('2. El sistema en una página'));
c.push(P('Ninguna orden llega directo a los motores: todo pasa antes por el supervisor. La única excepción es la parada de emergencia, que va de la GUI directo al firmware para que funcione aunque el supervisor falle.'));
c.push(...codigo([
  'ÓRDENES',
  '  GUI ─/cmd_vel─────────────→ supervisor ─/cmd_vel_safe────→ cinemática',
  '  cinemática ─/cmd_motors───→ firmware → motores N20',
  '  GUI ─/suction_gui_request─→ supervisor ─/suction_override→ succión',
  '  succión ─/cmd_suction/*───→ firmware → turbinas',
  '  GUI ─/e_stop──────────────→ firmware y supervisor (parada del operador)',
  '  supervisor ─/heartbeat────→ firmware (watchdog)',
  '',
  'SENSORES E INFORMACIÓN',
  '  firmware ─/imu/*/data─────→ supervisor, succión y estimador',
  '  estimador ─/joint_states, /tf→ robot_state_publisher → RViz2',
  '  firmware ─/battery/state──→ supervisor y GUI',
  '  supervisor ─/gui/notifications→ GUI',
  '  firmware (núcleo 0) ══video HTTP MJPEG══→ GUI (fuera de ROS 2)',
]));
c.push(H2('2.1 Los nodos y lo que hace cada uno'));
c.push(tabla([2600, 7038], ['Nodo', 'Qué hace'], [
  ['custom_gui_node', 'Interfaz del operador: movimiento, petición de succión, parada y liberación, modo prueba, estado del robot, batería tipo celular, notificaciones y video.'],
  ['state_machine_node (supervisor)', 'Decide si el robot está en SUELO, TRANSICIÓN o PARED; limita velocidad y succión; envía el heartbeat al firmware y notifica todo a la GUI. No activa la parada: eso lo decide solo el operador.'],
  ['kinematics_node', 'Convierte la velocidad del robot (m/s y rad/s) en la potencia de los motores izquierdo y derecho (−1 a 1).'],
  ['suction_control_node', 'Calcula la succión de cada turbina según la inclinación de su módulo; el supervisor solo puede subirla.'],
  ['joint_state_estimator_node', 'Calcula el ángulo de la articulación central con las dos IMU y la inclinación del robot para RViz2.'],
  ['robot_state_publisher', 'Nodo estándar de ROS 2: con el URDF y /joint_states calcula la posición de cada pieza.'],
  ['micro_ros_esp32_node (firmware)', 'Lee IMU y batería, mueve motores y turbinas con rampas, vigila el heartbeat y la parada, y transmite el video.'],
]));
c.push(H2('2.2 El video'));
c.push(P('Tal como dice la arquitectura, el video **no pasa por ROS 2**: sale directo del núcleo 0 de la ESP32 por HTTP. Al arrancar, el firmware muestra su IP por el monitor serie y ofrece tres direcciones:'));
c.push(B('`http://<ip-robot>/`: página con el video, para abrirla en cualquier navegador.'));
c.push(B('`http://<ip-robot>:81/stream`: video MJPEG; es la dirección que se le pasa a la GUI con `url_video`.'));
c.push(B('`http://<ip-robot>/foto`: una foto JPEG suelta.'));
c.push(nota('Límite:', 'el servidor de la ESP32 atiende **un solo cliente de video a la vez**. Si la GUI está mostrando el video, otro dispositivo no lo verá al mismo tiempo. Para verlo en varios equipos haría falta un nodo en el PC que lo lea una vez y lo reparta (sección 12.4 de la arquitectura); hoy no está en el grafo y no está implementado.'));
c.push(H2('2.3 Reglas de seguridad del firmware'));
c.push(tabla([2300, 2400, 4938], ['Modo', 'Cuándo', 'Qué hace'], [
  ['ESPERANDO', 'Desde que se enciende hasta el primer heartbeat', 'Nada se mueve: motores parados y turbinas apagadas. LED azul (o naranja si no hay agente).'],
  ['NORMAL', 'Llega el heartbeat y no hay parada', 'Aplica las órdenes de motores y turbinas con rampas. LED verde.'],
  ['PARADA', 'El operador activó la parada', 'Motores frenados al instante. Turbinas al máximo si el robot no está en el suelo; apagadas si está en el suelo. LED rojo.'],
  ['MODO SEGURO', 'Más de 500 ms sin heartbeat (supervisor caído o Wi-Fi perdido)', 'Igual que PARADA. Vuelve solo a NORMAL cuando regresa el heartbeat. LED rojo.'],
]));

// 3
c.push(H1('3. Qué hay en el repositorio'));
c.push(H2('3.1 Las carpetas'));
c.push(tabla([3300, 6338], ['Carpeta o archivo', 'Qué contiene'], [
  ['README.md', 'Descripción general del proyecto, requisitos, instalación y cómo correr todo.'],
  ['docs/Anteproyecto, Lista de materiales', 'El planteamiento del proyecto y los componentes a comprar.'],
  ['docs/arquitectura/', 'Documento de arquitectura y los grafos de nodos del robot real y de la simulación.'],
  ['docs/electronica/', 'Documento de conexiones, tabla con los 50 cables (CSV), diagrama de alimentación y de señales (draw.io y PNG).'],
  ['docs/guias/', 'Esta guía de estudio.'],
  ['docs/simulacion/', 'Documento de la simulación en Gazebo.'],
  ['docs/cinematica/CAD/', 'Ensamble de SolidWorks y su exportación a URDF. No se sube a GitHub por su tamaño.'],
  ['docs/*.png', 'Pinouts de la placa ESP32-S3 y de los módulos DRV8833, INA226 y MPU6050.'],
  ['ros2_ws/src/carro_trepador_interfaces', 'Mensaje propio Notificacion.msg.'],
  ['ros2_ws/src/carro_trepador_control', 'Supervisor, cinemática, succión y estimador de postura, con sus pruebas.'],
  ['ros2_ws/src/carro_trepador_teleop', 'Interfaz del operador.'],
  ['ros2_ws/src/carro_trepador_bringup', 'Launch, parámetros, configuración de RViz2 y firmware simulado.'],
  ['ros2_ws/src/carro_trepador_description', 'Modelo URDF con las mallas de SolidWorks y display.launch.py (RViz2 con deslizadores para mover las articulaciones).'],
  ['ros2_ws/src/carro_trepador_simulation', 'Simulación en Gazebo (launch, mundo y sim_bridge_node). Sin probar a fondo: está en pausa mientras se trabaja con el robot real.'],
  ['firmware/', 'Proyecto de PlatformIO de la ESP32-S3: firmware del robot, drivers y programas de prueba.'],
  ['scripts/', 'adaptar_urdf_solidworks.py (convierte la exportación de SolidWorks), diagrama_alimentacion.py (dibuja el diagrama de alimentación) y generar_guia_estudio.js (genera esta guía).'],
  ['matlab/, hardware/', 'Reservadas para modelos matemáticos y archivos de fabricación; por ahora vacías.'],
]));
c.push(H2('3.2 Software del PC (ros2_ws/src)'));
c.push(tabla([4000, 1000, 4638], ['Archivo', 'Líneas', 'Qué hace'], [
  ['carro_trepador_control/kinematics_node.py', '65', 'Cinemática diferencial: /cmd_vel_safe → /cmd_motors.'],
  ['carro_trepador_control/control/imu.py', '56', 'Inclinación, cabeceo y alabeo a partir de un mensaje de IMU. Lo usan los demás nodos.'],
  ['carro_trepador_control/suction_control_node.py', '125', 'Succión automática por inclinación, con rampa y con el override del supervisor.'],
  ['carro_trepador_control/joint_state_estimator_node.py', '123', 'Ángulo de la articulación central y /tf para RViz2.'],
  ['carro_trepador_control/state_machine_node.py', '323', 'Supervisor: estados, límites, modo prueba, heartbeat y notificaciones.'],
  ['carro_trepador_teleop/custom_gui_node.py', '509', 'Interfaz PyQt5 del operador.'],
  ['carro_trepador_interfaces/msg/Notificacion.msg', '—', 'Mensaje propio de las notificaciones (INFO, AVISO, ALERTA).'],
  ['carro_trepador_bringup/launch/bringup.launch.py', '78', 'Arranca todo el sistema con un solo comando.'],
  ['carro_trepador_bringup/config/parametros.yaml', '—', 'Parámetros de todos los nodos en un solo lugar.'],
  ['carro_trepador_bringup/rviz/robot.rviz', '—', 'Configuración de RViz2 con el marco fijo odom.'],
  ['carro_trepador_bringup/firmware_simulado.py', '182', 'Herramienta de prueba: hace de ESP32 en el PC. No es parte de la arquitectura.'],
  ['carro_trepador_control/test/*.py', '~250', 'Pruebas unitarias y de integración (sección 4.5).'],
]));
c.push(H2('3.3 Firmware (firmware/)'));
c.push(tabla([4000, 1000, 4638], ['Archivo', 'Líneas', 'Qué hace'], [
  ['platformio.ini', '—', 'Configuración de PlatformIO: un entorno para el robot y uno por cada prueba de hardware.'],
  ['include/pines.h', '82', 'Mapa de pines y canales PWM, con el motivo de cada elección.'],
  ['include/credenciales_wifi.ejemplo.h', '—', 'Plantilla de la red Wi-Fi y la IP del PC (agente).'],
  ['lib/Rampa/Rampa.h', '69', 'Limitador de pendiente: arranques y frenadas graduales.'],
  ['lib/Mpu6050/', '148', 'Driver de la IMU con interrupción de dato listo.'],
  ['lib/Ina226/', '143', 'Driver del medidor de voltaje y corriente.'],
  ['lib/Drv8833/', '146', 'Driver del puente H de los motores, con rampa.'],
  ['lib/EscPwm/', '93', 'Señal de 50 Hz para los ESC de las turbinas, con rampa.'],
  ['lib/FiltroOrientacion/FiltroOrientacion.h', '81', 'Filtro de Mahony: orientación a partir de giroscopio y acelerómetro.'],
  ['src/main.cpp', '511', 'Firmware del robot (micro_ros_esp32_node): micro-ROS, sensores, actuadores y seguridad.'],
  ['src/robot/video.cpp', '118', 'Cámara OV2640 y servidor de video en el núcleo 0.'],
  ['src/pruebas/*.cpp', '—', 'Un programa por componente: cámara, IMU, motores, INA226 y ESC.'],
]));

// 4
c.push(H1('4. Ruta de estudio'));
c.push(P('La idea es avanzar de lo simple a lo complejo y, en cada paso, **ejecutar** el código además de leerlo. Leer sin ejecutar se olvida rápido; ver un número cambiar en la terminal se queda.'));
c.push(H2('4.1 Etapa 0: el panorama (1 hora)'));
c.push(N('Abre el grafo **grafo nodos microproyecto.drawio.png** y el documento de arquitectura.', 'e0'));
c.push(N('Repasa la sección 2 de esta guía y ubica cada nodo en el grafo.', 'e0'));
c.push(N('Durante todo el estudio, cada vez que leas un nodo, búscalo en el grafo: qué recibe y qué publica.', 'e0'));
c.push(H2('4.2 Etapa 1: lo básico de ROS 2 (2 o 3 días)'));
c.push(P('Haz los tutoriales oficiales de ROS 2 Humble en **docs.ros.org/en/humble/Tutorials.html**. Con ellos se entiende la mayor parte del código del PC:'));
c.push(B('**Beginner: CLI tools:** nodos, tópicos, servicios, parámetros, rqt y launch.'));
c.push(B('**Beginner: Client libraries:** «Writing a simple publisher and subscriber (Python)», «Writing a simple service and client (Python)» y «Using parameters in a class (Python)».'));
c.push(B('**Intermediate: tf2:** solo «Introducing tf2», para entender /tf y RViz2.'));
c.push(P('Conceptos que debes dominar al terminar: nodo, tópico, mensaje, servicio, parámetro, QoS, launch y TF (ver el glosario de la sección 8).'));
c.push(H2('4.3 Etapa 2: los nodos del PC, en este orden'));
c.push(tabla([3000, 3300, 3338], ['Archivo', 'Qué aprendes', 'Pregunta guía'], [
  ['1. kinematics_node.py', 'La estructura de un nodo: suscribirse, calcular y publicar.', 'P1. ¿Qué publica si pido 0.5 m/s y 2 rad/s a la vez?'],
  ['2. control/imu.py', 'Cuaterniones y ángulos de inclinación.', 'P2. ¿Por qué hay dos formas de calcular cada ángulo?'],
  ['3. suction_control_node.py', 'Timers, rampas y combinar dos fuentes con max().', 'P3. ¿Por qué la succión baja más lento de lo que sube?'],
  ['4. joint_state_estimator_node.py', '/joint_states, /tf y robot_state_publisher.', 'P4. ¿Por qué el robot no avanza en RViz2 aunque el real sí?'],
  ['5. state_machine_node.py', 'Máquina de estados, QoS, servicios e histéresis.', 'P5. ¿Para qué sirven los ±5° alrededor de los umbrales?'],
  ['6. custom_gui_node.py', 'PyQt5 y cómo convive con ROS 2 (un timer que llama spin_once).', 'P6. ¿Por qué /cmd_vel se publica aunque sea cero?'],
  ['7. bringup.launch.py y parametros.yaml', 'Launch con argumentos y condiciones.', 'P7. ¿Qué cambia con simulado:=true?'],
]));
c.push(espacio());
c.push(P('Para cada nodo, arranca el sistema simulado y obsérvalo desde afuera:'));
c.push(...codigo([
  'ros2 launch carro_trepador_bringup bringup.launch.py simulado:=true',
  'rqt_graph                                  # el grafo real: compáralo con tu drawio',
  'ros2 node info /suction_control_node       # qué publica y qué recibe',
  'ros2 topic echo /cmd_suction/front         # los valores en vivo',
  'ros2 param set /firmware_simulado inclinacion_delantera 45.0',
]));
c.push(H2('4.4 Etapa 3: el firmware, en este orden'));
c.push(N('**include/pines.h:** qué hay conectado a cada pin y por qué. Ya lo conoces por el diagrama de conexiones.', 'e3'));
c.push(N('**lib/Rampa/Rampa.h:** la idea que más se repite en el firmware. Es corto y no depende de nada.', 'e3'));
c.push(N('**Los programas de src/pruebas/:** cada uno usa un solo driver. Súbelos a la placa mientras los lees (sección 5.3).', 'e3'));
c.push(N('**src/main.cpp**, por funciones:', 'e3'));
c.push(B('`setup()`: el orden de arranque. P8. ¿Por qué los ESC se inician primero?', 1));
c.push(B('`loop()`: lo que se hace en cada vuelta, sin esperas.', 1));
c.push(B('`atenderAgente()`: la conexión con el PC y la reconexión automática (máquina de estados).', 1));
c.push(B('`aplicarActuadores()`: **la seguridad**. Es la función más importante del firmware. P9. ¿Qué pasa con las turbinas si se corta el Wi-Fi con el robot en la pared?', 1));
c.push(N('**lib/FiltroOrientacion/FiltroOrientacion.h:** al final. Busca primero un video de «complementary filter IMU» y luego «Mahony filter». No hace falta entender cada fórmula, sino la idea: el giroscopio es rápido pero se desvía; el acelerómetro sabe dónde está abajo y corrige ese desvío.', 'e3'));
c.push(N('**src/robot/video.cpp:** cómo se arma un video MJPEG (una imagen JPEG tras otra, separadas por un límite).', 'e3'));
c.push(P('Para micro-ROS, el tutorial oficial está en **micro.ros.org** (Tutorials → micro-ROS for Arduino / PlatformIO): ahí aparece el mismo patrón de crear entidades y vigilar al agente que usa `main.cpp`.'));
c.push(H2('4.5 Etapa 4: las pruebas (aprende rompiendo)'));
c.push(P('Una **prueba unitaria** es un programa que llama a una función con datos conocidos y revisa que el resultado sea el esperado. Por ejemplo, `test_succion.py` comprueba que con 45° de inclinación la succión sea 35 %. Si mañana cambias el código y rompes algo, la prueba falla y te avisa antes de que lo descubras con el robot en la pared.'));
c.push(P('Una **prueba de integración** pone a funcionar varias piezas juntas. `test_supervisor.py` corre el supervisor de verdad con ROS 2, le envía IMU y órdenes falsas, y revisa lo que publica.'));
c.push(tabla([2700, 6938], ['Archivo', 'Qué prueba'], [
  ['test_cinematica.py', 'Quieto, avanzar y retroceder, girar en el sitio y que ninguna rueda pase de 100 % sin cambiar la curva.'],
  ['test_succion.py', 'Succión en el suelo, en la pared y en medio; que nunca baje al inclinarse más.'],
  ['test_imu.py', 'Inclinación, cabeceo y alabeo con acelerómetro y con cuaternión; que no invente un ángulo sin datos.'],
  ['test_estimador.py', 'Conversión de ángulos a cuaternión.'],
  ['test_supervisor.py', 'Integración: límite de velocidad, parada y liberación, succión mínima en la pared y GUI caída.'],
  ['test_flake8.py, test_pep257.py', 'Formato del código según las reglas de ROS 2 (líneas de máximo 99 caracteres, documentación).'],
]));
c.push(H3('Ejercicios'));
c.push(N('Corre la prueba más simple y lee su salida: `python3 -m pytest src/carro_trepador_control/test/test_cinematica.py -v`.', 'ej'));
c.push(N('**Rompe el código a propósito:** en kinematics_node.py cambia `/ 2.0` por `/ 3.0` y vuelve a correr la prueba. Mira cuál falla y por qué. Después deshaz el cambio.', 'ej'));
c.push(N('**Escribe tu propia prueba** en test_succion.py: que a 35° la succión sea 17.5 %.', 'ej'));
c.push(N('Cambia `succion_pared` en parametros.yaml, recompila (`colcon build`) y observa el cambio con el sistema simulado.', 'ej'));

// 5
c.push(H1('5. Cómo probar parte por parte'));
c.push(P('Las pruebas van de lo más seguro a lo más arriesgado. No pases al siguiente nivel hasta que el anterior funcione.'));
c.push(H2('5.1 Nivel 1: pruebas automáticas (sin robot, segundos)'));
c.push(...codigo([
  'cd ~/Carro_trepador/ros2_ws',
  'colcon build && source install/setup.bash',
  'colcon test && colcon test-result --verbose',
]));
c.push(P('Resultado esperado: **38 tests, 0 errors, 0 failures, 3 skipped**. Los 3 omitidos son las revisiones de licencia, que vienen desactivadas en ROS 2.'));
c.push(H2('5.2 Nivel 2: el sistema completo sin robot (minutos)'));
c.push(...codigo([
  'ros2 launch carro_trepador_bringup bringup.launch.py simulado:=true',
  '# en otra terminal, simular que el robot sube a la pared:',
  'ros2 param set /firmware_simulado inclinacion_delantera 90.0',
  'ros2 param set /firmware_simulado inclinacion_trasera 90.0',
]));
c.push(CASILLA('La GUI muestra «Robot conectado» y la batería.'));
c.push(CASILLA('Con W el robot avanza: la orden aparece en la GUI y en `ros2 topic echo /cmd_motors`.'));
c.push(CASILLA('El estado cambia a TRANSICIÓN y luego a PARED; en RViz2 el robot se dobla y luego queda vertical.'));
c.push(CASILLA('Espacio activa la parada; «Liberar parada» solo funciona con los controles sueltos.'));
c.push(CASILLA('Al cerrar la GUI aparece la notificación de órdenes detenidas (en el log del supervisor).'));
c.push(CASILLA('`imu_delantera_activa:=false` genera el aviso de IMU sin datos.'));
c.push(H2('5.3 Nivel 3: el hardware, un componente a la vez'));
c.push(nota('PlatformIO:', 'el comando `pio` instalado en el sistema es una versión antigua (4.3.4) y falla con este proyecto. Usa el botón de PlatformIO en VS Code o la ruta completa `~/.platformio/penv/bin/pio`.'));
c.push(nota('Puerto USB:', 'se programa por el USB-C marcado **COM** (chip CH343), que en Linux aparece como `/dev/ttyACM0`. Mientras el USB esté conectado, desconectar el rojo del BEC trasero: la ESP32 nunca debe recibir 5 V de dos fuentes a la vez.'));
c.push(tabla([600, 3700, 5338], ['#', 'Entorno (en firmware/)', 'Qué revisar'], [
  ['1', 'prueba_imus', 'Las dos IMU responden (0x68 y 0x69), INT cerca de 100 Hz, az ≈ 9.8 m/s² con el robot plano.'],
  ['2', 'prueba_potencia', 'El voltaje coincide con el multímetro. Ajustar R_SHUNT y CORRIENTE_MAX al shunt instalado.'],
  ['3', 'prueba_motores', 'Con las ruedas en el aire: on y luego w; los dos lados giran hacia adelante.'],
  ['4', 'prueba_esc', 'Sin hélices o con el robot sujeto: armado con pitidos y la turbina sube suave.'],
  ['5', 'prueba_camara', 'El video se ve en el navegador.'],
]));
c.push(espacio());
c.push(P('Cada prueba se sube y se abre el monitor serie así (cambiando el nombre del entorno):'));
c.push(...codigo(['~/.platformio/penv/bin/pio run -e prueba_imus -t upload', '~/.platformio/penv/bin/pio device monitor']));
c.push(H2('5.4 Nivel 4: el firmware real conectado a ROS 2'));
c.push(N('Copia `firmware/include/credenciales_wifi.ejemplo.h` como `credenciales_wifi.h` y pon tu red Wi-Fi y la IP del PC (se ve con `hostname -I` y se escribe con comas: `192, 168, 1, 100`). La red debe ser de **2.4 GHz** y la misma para el PC y la ESP32; las redes de la universidad con usuario o página de inicio no sirven (usar el punto de acceso del celular).', 'n4'));
c.push(N('Sube el firmware **con las turbinas sin hélices** y las ruedas en el aire:', 'n4'));
c.push(...codigo(['~/.platformio/penv/bin/pio run -e esp32s3_cam -t upload', '~/.platformio/penv/bin/pio device monitor']));
c.push(P('El monitor debe mostrar las IMU, el INA226 y la cámara como «ok», y luego la IP del robot y la dirección del video.'));
c.push(N('Carga el agente de micro-ROS (ya compilado en ~/microros_ws) y lanza todo:', 'n4'));
c.push(...codigo([
  'source ~/microros_ws/install/setup.bash',
  'ros2 launch carro_trepador_bringup bringup.launch.py \\',
  '    url_video:=http://<ip-robot>:81/stream',
]));
c.push(nota('Ojo con los < >:', 'en los comandos, lo que va entre `<` y `>` se reemplaza **completo, sin los signos**. Por ejemplo `url_video:=http://192.168.53.20:81/stream`. Si se escriben los signos, la terminal los interpreta como «leer de un archivo» y responde «No existe el archivo o el directorio».'));
c.push(P('El LED de la placa debe pasar de naranja (sin agente) a verde (normal).'));
c.push(N('**Prueba la seguridad antes de poner hélices:**', 'n4'));
c.push(CASILLA('Espacio: las ruedas paran al instante y el LED se pone rojo.'));
c.push(CASILLA('Ctrl+C en el launch: en menos de 0.5 s el robot entra en modo seguro (LED rojo, ruedas paradas).'));
c.push(CASILLA('Con el robot inclinado a mano, las turbinas suben; en el suelo se apagan.'));
c.push(CASILLA('Al volver a lanzar, el firmware se reconecta solo.'));
c.push(N('Cuando todo lo anterior funcione: hélices, primero con `TURBINA_TOPE` bajo en main.cpp (por ejemplo 0.4f), luego en el suelo y al final en la pared.', 'n4'));

// 6
c.push(H1('6. Respuestas a las preguntas guía'));
c.push(P('Intenta responder cada pregunta antes de leer la respuesta.'));
const resp = [
  ['P1. ¿Qué publica kinematics_node si pido 0.5 m/s y 2 rad/s?', 'Sin límite, la rueda izquierda iría a (0.5 − 2·0.0829)/0.39 = 0.86 y la derecha a (0.5 + 2·0.0829)/0.39 = 1.71 (0.39 m/s es la velocidad máxima de rueda de los N20 a 5 V). Como la derecha pasa de 1, las dos se dividen por 1.71: quedan 0.50 y 1.00. Se conserva la proporción entre ruedas, así que el robot sigue la misma curva, solo que más despacio. (En el sistema completo, el supervisor ya habría limitado antes la velocidad a 0.25 m/s.)'],
  ['P2. ¿Por qué hay dos formas de calcular cada ángulo?', 'Si el mensaje trae orientación (el firmware la calcula con el filtro de Mahony), se usa esa, porque es más estable. Si no la trae (orientation_covariance[0] = −1, la convención de ROS), se calcula solo con el acelerómetro, que vale mientras el robot no acelere fuerte.'],
  ['P3. ¿Por qué la succión baja más lento de lo que sube?', 'Subir rápido sirve para agarrarse cuanto antes al empezar a trepar. Bajar despacio evita que el robot se suelte de golpe por un cambio brusco y reduce los picos de corriente en los ESC.'],
  ['P4. ¿Por qué el robot no avanza en RViz2?', 'Para saber cuánto avanzó haría falta odometría (encoders en las ruedas) y para saber su rumbo un magnetómetro. El robot no tiene ninguno de los dos, así que RViz2 lo dibuja siempre en el origen. Lo que sí se ve igual que en la realidad es la inclinación y cómo se dobla la articulación.'],
  ['P5. ¿Para qué sirven los ±5° alrededor de los umbrales?', 'Es histéresis. Si el robot está justo en 25°, la vibración haría saltar el estado entre SUELO y TRANSICIÓN muchas veces por segundo, con una notificación en cada salto. Con ±5°, para pasar a TRANSICIÓN hay que superar 30° y para volver a SUELO hay que bajar de 20°.'],
  ['P6. ¿Por qué /cmd_vel se publica aunque sea cero?', 'Así el supervisor sabe que la GUI sigue viva. Si deja de recibir /cmd_vel por 0.5 s (la GUI se cerró o se colgó), pone la velocidad en cero y avisa. Si la GUI solo publicara al moverse, el supervisor no podría distinguir «quieto» de «GUI caída».'],
  ['P7. ¿Qué cambia con simulado:=true?', 'El launch no arranca el agente de micro-ROS (no hay ESP32) y en su lugar arranca firmware_simulado, que publica y recibe los mismos tópicos que el firmware real. Los demás nodos no se enteran de la diferencia.'],
  ['P8. ¿Por qué los ESC se inician primero en setup()?', 'Un ESC solo se arma si al recibir batería ve la señal de 0 % (pulso de 1000 µs). Si la ESP32 tardara en empezar a mandar la señal, el ESC podría quedar sin armar o, peor, leer un pulso cualquiera. Por eso es lo primero que se configura.'],
  ['P9. ¿Qué pasa con las turbinas si se corta el Wi-Fi con el robot en la pared?', 'Deja de llegar el heartbeat; a los 500 ms el firmware entra en MODO SEGURO: frena los motores y, como las IMU dicen que no está en el suelo, sube las turbinas al máximo para que quede pegado. Cuando vuelve la conexión y el heartbeat, regresa solo a NORMAL.'],
];
for (const [q, a] of resp) {
  c.push(new Paragraph({ children: [new TextRun({ text: q, bold: true, color: TITULO })], spacing: { before: 160, after: 60 } }));
  c.push(P(a));
}

// 7
c.push(H1('7. Comandos útiles'));
c.push(tabla([4600, 5038], ['Comando', 'Para qué sirve'], [
  ['colcon build && source install/setup.bash', 'Compilar el workspace y cargarlo en la terminal.'],
  ['ros2 launch carro_trepador_bringup bringup.launch.py simulado:=true', 'Todo el sistema sin robot.'],
  ['ros2 node list', 'Qué nodos están corriendo.'],
  ['ros2 node info /<nodo>', 'Qué publica, recibe y ofrece un nodo.'],
  ['ros2 topic list / ros2 topic echo <tópico>', 'Ver los tópicos y sus mensajes en vivo.'],
  ['ros2 topic hz <tópico>', 'Frecuencia real de un tópico (las IMU deben estar cerca de 50 a 100 Hz).'],
  ['ros2 param list / ros2 param set /<nodo> <param> <valor>', 'Ver y cambiar parámetros en vivo.'],
  ['ros2 service call /set_test_mode std_srvs/srv/SetBool "{data: true}"', 'Activar el modo prueba sin la GUI.'],
  ['rqt_graph', 'Dibujo del grafo real de nodos y tópicos.'],
  ['colcon test && colcon test-result --verbose', 'Correr todas las pruebas.'],
  ['python3 -m pytest <archivo> -v', 'Correr un archivo de pruebas con detalle.'],
  ['~/.platformio/penv/bin/pio run -e <entorno> -t upload', 'Compilar y subir el firmware o una prueba.'],
  ['~/.platformio/penv/bin/pio device monitor', 'Ver el monitor serie de la ESP32.'],
]));

// 8
c.push(H1('8. Glosario'));
const glos = [
  ['Nodo', 'Un programa de ROS 2 con una tarea. Se comunica con los otros por tópicos y servicios.'],
  ['Tópico', 'Canal con nombre (por ejemplo /cmd_vel) por el que un nodo publica mensajes y otros los reciben.'],
  ['Mensaje', 'La estructura de datos que viaja por un tópico (por ejemplo sensor_msgs/Imu).'],
  ['Servicio', 'Pregunta y respuesta entre dos nodos. Se usa en /set_test_mode: la GUI pide y el supervisor acepta o rechaza.'],
  ['Parámetro', 'Un valor de configuración de un nodo que se puede cambiar sin tocar el código (parametros.yaml o ros2 param set).'],
  ['QoS', 'Reglas de entrega de un tópico. Reliable: se reenvía hasta que llega (parada de emergencia). Best effort: si se pierde, llega el siguiente (IMU y batería). Transient local: el que llega tarde recibe los últimos mensajes (notificaciones).'],
  ['Launch', 'Archivo que arranca varios nodos a la vez con sus parámetros.'],
  ['TF', 'El árbol de transformaciones: dónde está y cómo está girada cada pieza respecto a las demás.'],
  ['URDF', 'Descripción del robot (piezas, articulaciones y mallas) que usan RViz2 y Gazebo.'],
  ['micro-ROS y agente', 'micro-ROS es ROS 2 para microcontroladores. El agente es el programa del PC que conecta la ESP32 (por Wi-Fi/UDP) con el resto de ROS 2.'],
  ['Heartbeat y watchdog', 'El supervisor envía un «sigo vivo» 10 veces por segundo; el watchdog del firmware entra en modo seguro si deja de llegar por 500 ms.'],
  ['Histéresis', 'Usar umbrales distintos para entrar y salir de un estado, para que no salte de un lado a otro.'],
  ['Rampa', 'Cambiar un valor de forma gradual hasta su objetivo, a una velocidad máxima.'],
  ['BEC', 'Regulador de 5 V que traen los ESC. En este robot el del ESC delantero alimenta el DRV8833 y el del trasero la ESP32. Son lineales: se calientan.'],
  ['Cuaternión', 'Cuatro números (w, x, y, z) que representan una orientación sin los problemas de los ángulos a 90°.'],
  ['Filtro de Mahony', 'Combina giroscopio y acelerómetro para estimar la orientación de cada IMU.'],
  ['MJPEG', 'Video hecho de imágenes JPEG enviadas una tras otra por HTTP.'],
  ['PWM y LEDC', 'PWM es una señal que se prende y apaga muy rápido para regular potencia. LEDC es el periférico de la ESP32 que la genera.'],
];
c.push(tabla([2600, 7038], ['Término', 'Significado'], glos));

// 9
c.push(H1b('9. Consejos para estudiar'));
c.push(B('Estudia por sesiones cortas, un archivo a la vez, y escribe con tus palabras qué hace antes de pasar al siguiente.'));
c.push(B('Antes de cambiar algo, corre las pruebas; después de cambiarlo, córrelas otra vez.'));
c.push(B('Si no entiendes una línea, pregunta señalando el archivo y el número de línea (por ejemplo, state_machine_node.py, línea 257) para recibir la explicación con su contexto.'));
c.push(B('Cuando pruebes con hardware, una sola cosa nueva a la vez, y siempre la seguridad primero: hélices fuera, ruedas en el aire y la parada a mano.'));

// ---------- documento ----------
const doc = new Document({
  features: { updateFields: true },
  creator: 'Juan Sebastián Castaño Aros',
  title: 'Guía de estudio del software - Carro Trepador',
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, color: TITULO }, paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0, keepNext: true, keepLines: true } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, color: '2E74B5' }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1, keepNext: true, keepLines: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 23, bold: true, color: '2E74B5' }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2, keepNext: true, keepLines: true } },
    ],
  },
  numbering: {
    config: [
      { reference: 'vinetas', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
      ] },
      { reference: 'casillas', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '☐', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ] },
      ...['numeros', 'e0', 'e3', 'ej', 'n4'].map((r) => ({ reference: r, levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ] })),
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Carro Trepador · Guía de estudio del software', size: 16, color: '7F7F7F' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '7F7F7F' })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(process.argv[2], b);
  console.log('ok', process.argv[2]);
});
