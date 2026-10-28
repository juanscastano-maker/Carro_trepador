#!/usr/bin/env python3
"""
Adapta la exportación de SolidWorks (sw_urdf_exporter, ROS 1) al URDF de ROS 2 del proyecto.

Genera ros2_ws/src/carro_trepador_description/urdf/carro_trepador.urdf y copia las mallas a
carro_trepador_description/meshes/. Usarlo cada vez que se reexporte el ensamble desde SolidWorks.

Uso (desde la raíz del repositorio):
    python3 scripts/adaptar_urdf_solidworks.py --exportacion <carpeta exportada>
    # ejemplo:
    python3 scripts/adaptar_urdf_solidworks.py --exportacion ~/Drive/CAD/URDF/Ensamblaje1_juan

Después: cd ros2_ws && colcon build --symlink-install

Qué cambia respecto a la exportación (el porqué está en docs/simulacion):
    - Rutas de mallas a package://carro_trepador_description.
    - Ruedas traseras de fixed a continuous y ejes de las 6 ruedas invertidos.
    - base_link raíz sin inercia, marcos de las dos IMUs y colisiones simples.
    - Fricción anisotrópica de las llantas y bloques de Gazebo (IMUs, articulaciones, tracción).
    - Masas, inercias, posiciones y mallas visuales se copian tal cual de la exportación.

IMPORTANTE: el script depende de los NOMBRES de links y joints de la exportación actual
(chasis_trasero_link, rueda_media_izquierda_Link, chasis_trasero_joint, ...). Si se renombran en
SolidWorks, hay que actualizarlos aquí. Las medidas de las colisiones, la posición de las IMUs y la
separación entre ruedas también están escritas a mano: si cambia el diseño, revisarlas.
"""
import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESC = REPO / "ros2_ws" / "src" / "carro_trepador_description"
PKG = "package://carro_trepador_description/meshes/"

parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--exportacion", required=True, type=Path,
                    help="Carpeta del paquete exportado por SolidWorks (contiene urdf/ y meshes/)")
args = parser.parse_args()

exp = args.exportacion.expanduser().resolve()
urdfs = sorted((exp / "urdf").glob("*.urdf"))
if len(urdfs) != 1:
    raise SystemExit(f"Se esperaba un solo .urdf en {exp / 'urdf'}, se encontraron {len(urdfs)}")
SRC = urdfs[0]
DST = DESC / "urdf" / "carro_trepador.urdf"

root = ET.parse(SRC).getroot()
links = {lk.get("name"): lk for lk in root.findall("link")}
joints = {j.get("name"): j for j in root.findall("joint")}


def f(x):
    return f"{float(x):.6g}"


def vec(s):
    return " ".join(f(v) for v in s.split())


def inertial(link):
    i = link.find("inertial")
    o, m, t = i.find("origin"), i.find("mass"), i.find("inertia")
    a = {k: f(t.get(k)) for k in ["ixx", "ixy", "ixz", "iyy", "iyz", "izz"]}
    return (f'    <inertial>\n'
            f'      <origin xyz="{vec(o.get("xyz"))}" rpy="{vec(o.get("rpy"))}"/>\n'
            f'      <mass value="{f(m.get("value"))}"/>\n'
            f'      <inertia ixx="{a["ixx"]}" ixy="{a["ixy"]}" ixz="{a["ixz"]}" '
            f'iyy="{a["iyy"]}" iyz="{a["iyz"]}" izz="{a["izz"]}"/>\n'
            f'    </inertial>\n')


def visual(link):
    v = link.find("visual")
    mesh = v.find("geometry/mesh").get("filename").split("/")[-1]
    rgba = vec(v.find("material/color").get("rgba"))
    return (f'    <visual>\n'
            f'      <origin xyz="0 0 0" rpy="0 0 0"/>\n'
            f'      <geometry>\n        <mesh filename="{PKG}{mesh}"/>\n      </geometry>\n'
            f'      <material name="{link.get("name")}_color">\n'
            f'        <color rgba="{rgba}"/>\n      </material>\n'
            f'    </visual>\n')


def collision(xyz, rpy, geom):
    return (f'    <collision>\n'
            f'      <origin xyz="{xyz}" rpy="{rpy}"/>\n'
            f'      <geometry>\n        {geom}\n      </geometry>\n'
            f'    </collision>\n')


def link(name, coll=""):
    lk = links[name]
    return f'  <link name="{name}">\n' + inertial(lk) + visual(lk) + coll + '  </link>\n'


def joint_origin(name):
    o = joints[name].find("origin")
    return f'<origin xyz="{vec(o.get("xyz"))}" rpy="{vec(o.get("rpy"))}"/>'


WHEEL = '<cylinder radius="0.015" length="0.022"/>'


def wheel(name, joint, parent, side, comment):
    # La llanta ocupa 22 mm del eje local z: hacia -z en las derechas, hacia +z en las izquierdas
    z = "-0.011" if side == "der" else "0.011"
    out = f'  <!-- {comment} -->\n'
    out += link(name, collision(f"0 0 {z}", "0 0 0", WHEEL))
    out += (f'  <joint name="{joint}" type="continuous">\n'
            f'    {joint_origin(joint)}\n'
            f'    <parent link="{parent}"/>\n    <child link="{name}"/>\n'
            f'    <!-- Eje invertido respecto a la exportación: velocidad positiva = avanzar -->\n'
            f'    <axis xyz="0 0 -1"/>\n'
            f'    <dynamics damping="0.0001" friction="0.0"/>\n'
            f'  </joint>\n\n')
    return out


u = []
u.append('''<?xml version="1.0"?>
<!--
  Carro Trepador: modelo URDF para ROS 2 Humble (RViz y Gazebo Fortress).

  Origen: exportación de SolidWorks (sw_urdf_exporter) del ensamble Ensamblaje1_juan,
  adaptada a ROS 2. Cambios respecto a la exportación:
    - Rutas de mallas apuntan a carro_trepador_description (antes Ensamblaje1_juan).
    - Mallas visuales: las originales de SolidWorks, sin modificar.
    - Colisiones simplificadas: cajas para los chasis y cilindros para las ruedas.
    - Ruedas traseras pasan de fixed a continuous (giran libres, sin motor).
    - Ejes de las ruedas invertidos para que velocidad positiva = avanzar.
    - Agregados base_link (raíz sin inercia), marcos de las IMUs y bloques de Gazebo.
  Masas e inercias: las calculó SolidWorks; no se han verificado con el robot real.

  Convención de nombres (heredada de la exportación, se respeta tal cual en el código):
    chasis_trasero_joint = articulación central PASIVA entre los dos módulos.
    Algunos links terminan en "_Link" (L mayúscula) y otros en "_link".
-->
<robot name="carro_trepador">

  <!-- Raíz del robot, a nivel del suelo bajo el módulo trasero. Sin inercia porque
       KDL (robot_state_publisher) no admite inercia en el link raíz. -->
  <link name="base_link"/>
  <joint name="base_joint" type="fixed">
    <origin xyz="0 0 0.008" rpy="0 0 0"/>
    <parent link="base_link"/>
    <child link="chasis_trasero_link"/>
  </joint>

  <!-- ===================== Módulo trasero ===================== -->
  <!-- Colisión: caja del chasis, levantada 4 mm del suelo para que no roce al avanzar -->
''')
u.append(link("chasis_trasero_link",
              collision("0.0057 0 0.01465", "0 0 0", '<box size="0.163 0.18 0.0373"/>')))
u.append("\n")
u.append(wheel("rueda_trasera_derecha_link", "rueda_trasera_derecha_joint", "chasis_trasero_link",
               "der", "Rueda trasera derecha: LIBRE (sin motor)"))
u.append(wheel("rueda_trasera_izquierda_link", "rueda_trasera_izquierda_joint", "chasis_trasero_link",
               "izq", "Rueda trasera izquierda: LIBRE (sin motor)"))
u.append(wheel("rueda_media_derecha_link", "rueda_media_derecha_joint", "chasis_trasero_link",
               "der", "Rueda media derecha: MOTOR N20"))
u.append(wheel("rueda_media_izquierda_Link", "rueda_media_izquierda_joint", "chasis_trasero_link",
               "izq", "Rueda media izquierda: MOTOR N20"))

u.append('  <!-- Hélice de la turbina trasera (solo visual, sin colisión) -->\n')
u.append(link("helice_trasera_link"))
u.append(f'''  <joint name="helice_trasera_joint" type="continuous">
    {joint_origin("helice_trasera_joint")}
    <parent link="chasis_trasero_link"/>
    <child link="helice_trasera_link"/>
    <axis xyz="0 0 1"/>
  </joint>

  <!-- IMU trasera (GY-521 / MPU6050): posición del chip tomada del ensamble de SolidWorks.
       Placa plana, chip hacia arriba, lado largo hacia adelante, del lado derecho del módulo.
       Supuesto: el eje X del sensor apunta hacia adelante. Verificar con la serigrafía de la placa. -->
  <link name="imu_rear_link"/>
  <joint name="imu_rear_joint" type="fixed">
    <origin xyz="-0.0024 -0.054 0.0186" rpy="0 0 0"/>
    <parent link="chasis_trasero_link"/>
    <child link="imu_rear_link"/>
  </joint>

  <!-- ===================== Articulación central ===================== -->
  <!-- PASIVA: sin motor, el módulo delantero se dobla en pitch al pasar del suelo a la pared -->
  <joint name="chasis_trasero_joint" type="revolute">
    {joint_origin("chasis_trasero_joint")}
    <parent link="chasis_trasero_link"/>
    <child link="chasis_delantero_link"/>
    <axis xyz="0 0 1"/>
    <limit lower="-1.5708" upper="1.5708" effort="10" velocity="1"/>
    <dynamics damping="0.001" friction="0.0"/>
  </joint>

  <!-- ===================== Módulo delantero ===================== -->
  <!-- Su marco está girado 90° en x respecto al trasero: aquí y = arriba, z = lateral -->
''')
u.append(link("chasis_delantero_link",
              collision("0.0767 0.02345 -0.03", "0 0 0", '<box size="0.1614 0.0629 0.1818"/>')))
u.append("\n")
u.append(wheel("rueda_delantera_derecha_Link", "rueda_delantera_derecha_joint", "chasis_delantero_link",
               "der", "Rueda delantera derecha: MOTOR N20"))
u.append(wheel("rueda_delantera_izquierda_Link", "rueda_delantera_izquierda_joint", "chasis_delantero_link",
               "izq", "Rueda delantera izquierda: MOTOR N20"))
u.append('  <!-- Hélice de la turbina delantera (solo visual, sin colisión) -->\n')
u.append(link("helice_delantera_link"))
u.append(f'''  <joint name="helice_delantera_joint" type="continuous">
    {joint_origin("helice_delantera_joint")}
    <parent link="chasis_delantero_link"/>
    <child link="helice_delantera_link"/>
    <axis xyz="0 0 1"/>
  </joint>

  <!-- IMU delantera (GY-521 / MPU6050): posición del chip tomada del ensamble de SolidWorks.
       Placa plana, chip hacia arriba, lado largo hacia adelante, del lado derecho del módulo.
       El giro de -90° en x compensa el marco girado del chasis delantero (queda x adelante, z arriba).
       Mismo supuesto que la trasera sobre el eje X del sensor. -->
  <link name="imu_front_link"/>
  <joint name="imu_front_joint" type="fixed">
    <origin xyz="0.0245 0.0125 0.01" rpy="-1.5708 0 0"/>
    <parent link="chasis_delantero_link"/>
    <child link="imu_front_link"/>
  </joint>

  <!-- ===================== Gazebo (Fortress) ===================== -->
  <!-- RViz ignora estos bloques. -->

  <!-- Fricción de las llantas: alta al rodar (mu2 = 1.0) y baja de lado (mu1 = 0.3,
       en la dirección del eje, fdir1). Con fricción igual en todas las direcciones el
       robot NO gira en Gazebo: 6 ruedas en fila frenan el giro. Probado: con mu1 = 0.3
       gira bien; con 0.5 o más casi no gira. Ver nota en el README. -->
''')
for w in ["rueda_trasera_derecha_link", "rueda_trasera_izquierda_link", "rueda_media_derecha_link",
          "rueda_media_izquierda_Link", "rueda_delantera_derecha_Link", "rueda_delantera_izquierda_Link"]:
    u.append(f'  <gazebo reference="{w}">\n    <mu1>0.3</mu1>\n    <mu2>1.0</mu2>\n'
             f'    <fdir1>0 0 1</fdir1>\n  </gazebo>\n')
u.append('''
  <!-- Chasis con poca fricción, por si tocan el suelo en una transición -->
  <gazebo reference="chasis_trasero_link">
    <mu1>0.2</mu1>
    <mu2>0.2</mu2>
  </gazebo>
  <gazebo reference="chasis_delantero_link">
    <mu1>0.2</mu1>
    <mu2>0.2</mu2>
  </gazebo>

  <!-- IMUs simuladas. Publican en los mismos tópicos que el firmware real. -->
  <gazebo reference="imu_rear_link">
    <sensor name="imu_rear" type="imu">
      <always_on>true</always_on>
      <update_rate>100</update_rate>
      <topic>imu/rear/data</topic>
      <ignition_frame_id>imu_rear_link</ignition_frame_id>
    </sensor>
  </gazebo>
  <gazebo reference="imu_front_link">
    <sensor name="imu_front" type="imu">
      <always_on>true</always_on>
      <update_rate>100</update_rate>
      <topic>imu/front/data</topic>
      <ignition_frame_id>imu_front_link</ignition_frame_id>
    </sensor>
  </gazebo>

  <gazebo>
    <!-- Tracción solo para PRUEBAS en simulación: mueve las 4 ruedas con motor
         a partir de /sim/cmd_vel. No forma parte de la arquitectura del robot real. -->
    <plugin filename="ignition-gazebo-diff-drive-system" name="ignition::gazebo::systems::DiffDrive">
      <left_joint>rueda_media_izquierda_joint</left_joint>
      <left_joint>rueda_delantera_izquierda_joint</left_joint>
      <right_joint>rueda_media_derecha_joint</right_joint>
      <right_joint>rueda_delantera_derecha_joint</right_joint>
      <!-- Distancia entre los centros de las llantas (eje a ±93.9 mm, llanta 11 mm hacia adentro) -->
      <wheel_separation>0.1658</wheel_separation>
      <wheel_radius>0.015</wheel_radius>
      <topic>sim/cmd_vel</topic>
      <odom_topic>sim/odom</odom_topic>
      <frame_id>odom</frame_id>
      <child_frame_id>base_link</child_frame_id>
      <odom_publish_frequency>30</odom_publish_frequency>
    </plugin>

    <!-- Publica el ángulo de todas las articulaciones (incluida la central) -->
    <plugin filename="ignition-gazebo-joint-state-publisher-system" name="ignition::gazebo::systems::JointStatePublisher">
      <topic>joint_states</topic>
    </plugin>
  </gazebo>

</robot>
''')

DST.write_text("".join(u))
print("URDF escrito en", DST.relative_to(REPO))

# Copia las mallas que usa el URDF
mallas = DESC / "meshes"
mallas.mkdir(exist_ok=True)
for m in sorted((exp / "meshes").glob("*.STL")):
    shutil.copy2(m, mallas / m.name)
    print("malla copiada:", m.name)
