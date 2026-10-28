"""
Supervisor de seguridad del robot trepador (state_machine_node).

Responsabilidades (docs/arquitectura/Arquitectura_Carro_trepador_v5.docx):
  - Decidir el estado del robot (SUELO, TRANSICION, PARED) con las dos IMUs.
  - Validar las peticiones de la GUI: /cmd_vel -> /cmd_vel_safe y
    /suction_gui_request -> /suction_override.
  - Escuchar /e_stop (lo activa y libera SOLO el operador; el supervisor nunca lo publica).
  - Publicar /heartbeat a 10 Hz para el watchdog del firmware.
  - Atender /set_test_mode.
  - Notificar TODO por /gui/notifications (estado, órdenes, paradas, protecciones, batería,
    sensores).

Protecciones automáticas (no son paradas): timeout de /cmd_vel y succión mínima en pared.
"""

import math
import time

from carro_trepador_interfaces.msg import Notificacion
from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data, ReliabilityPolicy
from sensor_msgs.msg import BatteryState, Imu
from std_msgs.msg import Bool, Float32, UInt32
from std_srvs.srv import SetBool

from carro_trepador_control.control.imu import inclinacion

INFO, AVISO, ALERTA = Notificacion.INFO, Notificacion.AVISO, Notificacion.ALERTA

QOS_NOTIFICACIONES = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
QOS_CONFIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class StateMachineNode(Node):
    """Valida las peticiones de la GUI, decide el estado del robot y notifica todo."""

    def __init__(self):
        super().__init__('state_machine_node')
        p = self.declare_parameter
        self.v_max = p('velocidad_lineal_max', 0.25).value          # m/s
        self.w_max = p('velocidad_angular_max', 1.5).value          # rad/s
        self.factor_prueba = p('factor_modo_prueba', 0.3).value     # límite en modo prueba
        # más lento al cambiar de superficie
        self.factor_transicion = p('factor_transicion', 0.5).value
        self.succion_max_prueba = p('succion_max_modo_prueba', 30.0).value
        self.succion_min_pared = p('succion_min_pared', 60.0).value
        self.umbral_suelo = p('umbral_suelo_grados', 25.0).value
        self.umbral_pared = p('umbral_pared_grados', 65.0).value
        self.timeout_cmd = p('timeout_cmd_vel', 0.5).value
        self.timeout_imu = p('timeout_imu', 0.2).value
        self.timeout_firmware = p('timeout_firmware', 1.0).value
        self.celdas = p('celdas_bateria', 4).value

        # Estado
        self.estado = None            # SUELO, TRANSICION o PARED
        self.parada = False           # parada de emergencia activa (decidida por el operador)
        self.prueba = False           # modo prueba
        self.esperar_neutro = False   # tras liberar la parada, esperar /cmd_vel = 0
        self.cmd = Twist()
        self.t_cmd = None
        self.cmd_vencido = False
        self.succion_operador = 0.0
        self.inclinacion = {'delantera': None, 'trasera': None}
        self.t_imu = {'delantera': None, 'trasera': None}
        self.imu_ok = {'delantera': True, 'trasera': True}
        self.t_bateria = None
        self.firmware_ok = None       # None = todavía no llegó nada
        self.umbrales_bateria = {0.50: False, 0.30: False, 0.20: False, 0.15: False}
        self.celda_baja = False
        self.contador_heartbeat = 0
        self.ultima_notificacion = {}

        # Comunicación
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.pub_override = self.create_publisher(Float32, '/suction_override', 10)
        self.pub_heartbeat = self.create_publisher(UInt32, '/heartbeat', 10)
        self.pub_notif = self.create_publisher(Notificacion, '/gui/notifications',
                                               QOS_NOTIFICACIONES)

        self.create_subscription(Twist, '/cmd_vel', self.al_cmd_vel, 10)
        self.create_subscription(Float32, '/suction_gui_request', self.al_pedido_succion, 10)
        self.create_subscription(Bool, '/e_stop', self.al_e_stop, QOS_CONFIABLE)
        self.create_subscription(Imu, '/imu/front/data', lambda m: self.al_imu('delantera', m),
                                 qos_profile_sensor_data)
        self.create_subscription(Imu, '/imu/rear/data', lambda m: self.al_imu('trasera', m),
                                 qos_profile_sensor_data)
        self.create_subscription(BatteryState, '/battery/state', self.al_bateria,
                                 qos_profile_sensor_data)
        self.create_service(SetBool, '/set_test_mode', self.al_modo_prueba)

        self.create_timer(0.1, self.publicar_heartbeat)  # 10 Hz
        self.create_timer(0.05, self.ciclo)              # 20 Hz

        self.notificar(INFO, 'supervisor', 'SUPERVISOR_INICIADO',
                       'Supervisor iniciado. Esperando datos del robot.')

    # ------------------------------------------------------------------ notificaciones
    def notificar(self, nivel, origen, codigo, texto, cada=0.0):
        """
        Publica una notificación.

        Con cada > 0, no repite el mismo código antes de ese tiempo.
        """
        ahora = time.monotonic()
        if cada > 0 and ahora - self.ultima_notificacion.get(codigo, -1e9) < cada:
            return
        self.ultima_notificacion[codigo] = ahora
        n = Notificacion(nivel=nivel, origen=origen, codigo=codigo, texto=texto)
        n.stamp = self.get_clock().now().to_msg()
        self.pub_notif.publish(n)
        # En rclpy cada línea de registro debe usar siempre el mismo nivel: una llamada por nivel
        if nivel == ALERTA:
            self.get_logger().error(f'[{codigo}] {texto}')
        elif nivel == AVISO:
            self.get_logger().warn(f'[{codigo}] {texto}')
        else:
            self.get_logger().info(f'[{codigo}] {texto}')

    # ------------------------------------------------------------------ entradas
    def al_cmd_vel(self, msg):
        self.cmd = msg
        self.t_cmd = time.monotonic()
        if self.cmd_vencido:
            self.cmd_vencido = False
            self.notificar(INFO, 'supervisor', 'CMD_VEL_RECUPERADO',
                           'La interfaz volvió a enviar órdenes.')
        if self.esperar_neutro and abs(msg.linear.x) < 1e-3 and abs(msg.angular.z) < 1e-3:
            self.esperar_neutro = False

    def al_pedido_succion(self, msg):
        pedido = float(msg.data)
        if self.parada:
            self.notificar(AVISO, 'supervisor', 'SUCCION_RECHAZADA',
                           'Petición de succión rechazada: la parada de emergencia está activa.')
            return
        valor = max(0.0, min(100.0, pedido))
        if self.prueba and valor > self.succion_max_prueba:
            valor = self.succion_max_prueba
            self.notificar(AVISO, 'supervisor', 'SUCCION_LIMITADA',
                           f'Succión limitada a {valor:.0f} % en modo prueba '
                           f'(pedido {pedido:.0f} %).')
        elif self.estado in ('PARED', 'TRANSICION') and valor < self.succion_min_pared:
            valor = self.succion_min_pared
            self.notificar(AVISO, 'supervisor', 'SUCCION_LIMITADA',
                           f'Fuera del suelo la succión mínima es {valor:.0f} % '
                           f'(pedido {pedido:.0f} %).')
        else:
            self.notificar(INFO, 'supervisor', 'SUCCION_ACEPTADA',
                           f'Succión pedida: {valor:.0f} %.')
        self.succion_operador = valor

    def al_e_stop(self, msg):
        if msg.data and not self.parada:
            self.parada = True
            self.notificar(ALERTA, 'operador', 'PARADA_ACTIVADA',
                           'Parada de emergencia activada por el operador. Tracción detenida.')
        elif not msg.data and self.parada:
            self.parada = False
            self.esperar_neutro = True
            self.notificar(INFO, 'operador', 'PARADA_LIBERADA',
                           'Parada liberada por el operador. El robot espera una orden nueva.')

    def al_imu(self, modulo, msg):
        self.t_imu[modulo] = time.monotonic()
        self.inclinacion[modulo] = inclinacion(msg)
        if not self.imu_ok[modulo]:
            self.imu_ok[modulo] = True
            self.notificar(INFO, f'imu_{modulo}', f'IMU_{modulo.upper()}_OK',
                           f'IMU {modulo} recuperada.')

    def al_bateria(self, msg):
        self.t_bateria = time.monotonic()
        pct = msg.percentage
        if not math.isnan(pct):
            for umbral in sorted(self.umbrales_bateria, reverse=True):
                if pct < umbral and not self.umbrales_bateria[umbral]:
                    self.umbrales_bateria[umbral] = True
                    nivel = INFO if umbral >= 0.5 else AVISO if umbral >= 0.3 else ALERTA
                    texto = (f'Batería por debajo de {umbral * 100:.0f} % '
                             f'({pct * 100:.0f} %, {msg.voltage:.2f} V).')
                    if umbral <= 0.2:
                        texto += ' Conviene bajar el robot.'
                    self.notificar(nivel, 'bateria', f'BATERIA_{int(umbral * 100)}', texto)
                elif pct > umbral + 0.05:
                    self.umbrales_bateria[umbral] = False
        v_celda = msg.voltage / self.celdas if self.celdas else 0.0
        if 0.0 < v_celda < 3.5 and not self.celda_baja:
            self.celda_baja = True
            self.notificar(ALERTA, 'bateria', 'BATERIA_CELDA_BAJA',
                           f'Voltaje por celda bajo: {v_celda:.2f} V. Bajar el robot pronto.')
        elif v_celda > 3.6:
            self.celda_baja = False

    def al_modo_prueba(self, req, resp):
        if req.data:
            if self.parada:
                resp.success, resp.message = (False,
                                              'Primero hay que liberar la parada de emergencia.')
            elif self.estado != 'SUELO':
                resp.success, resp.message = (
                    False, 'El modo prueba solo se permite con el robot en el suelo.')
            else:
                self.prueba = True
                resp.success, resp.message = (
                    True, 'Modo prueba activado: velocidad y succión limitadas.')
                self.succion_operador = min(self.succion_operador, self.succion_max_prueba)
                self.notificar(INFO, 'supervisor', 'MODO_PRUEBA_ON', resp.message)
        else:
            self.prueba = False
            resp.success, resp.message = True, 'Modo prueba desactivado.'
            self.notificar(INFO, 'supervisor', 'MODO_PRUEBA_OFF', resp.message)
        if not resp.success:
            self.notificar(AVISO, 'supervisor', 'MODO_PRUEBA_RECHAZADO', resp.message)
        return resp

    # ------------------------------------------------------------------ ciclo de control
    def publicar_heartbeat(self):
        self.contador_heartbeat = (self.contador_heartbeat + 1) % (2 ** 32)
        self.pub_heartbeat.publish(UInt32(data=self.contador_heartbeat))

    def ciclo(self):
        ahora = time.monotonic()
        self.revisar_sensores(ahora)
        self.actualizar_estado()

        # Velocidad validada
        salida = Twist()
        vencido = self.t_cmd is None or ahora - self.t_cmd > self.timeout_cmd
        if vencido and self.t_cmd is not None and not self.cmd_vencido:
            self.cmd_vencido = True
            self.notificar(AVISO, 'supervisor', 'CMD_VEL_TIMEOUT',
                           'La interfaz dejó de enviar órdenes: robot detenido '
                           '(no es una parada de emergencia).')
        if not (self.parada or vencido or self.esperar_neutro or self.estado is None):
            factor = self.factor_prueba if self.prueba else 1.0
            if self.estado == 'TRANSICION':
                factor *= self.factor_transicion
            salida.linear.x = max(-self.v_max * factor,
                                  min(self.v_max * factor, self.cmd.linear.x))
            salida.angular.z = max(-self.w_max * factor,
                                   min(self.w_max * factor, self.cmd.angular.z))
        self.pub_cmd.publish(salida)

        # Succión: lo que pidió el operador, nunca por debajo del mínimo fuera del suelo
        override = self.succion_operador
        if self.estado in ('PARED', 'TRANSICION'):
            override = max(override, self.succion_min_pared)
        self.pub_override.publish(Float32(data=float(override)))

    def revisar_sensores(self, ahora):
        for modulo in ('delantera', 'trasera'):
            t = self.t_imu[modulo]
            if t is not None and ahora - t > self.timeout_imu and self.imu_ok[modulo]:
                self.imu_ok[modulo] = False
                self.notificar(AVISO, f'imu_{modulo}', f'IMU_{modulo.upper()}_SIN_DATOS',
                               f'IMU {modulo} sin datos por más de '
                               f'{self.timeout_imu * 1000:.0f} ms.')
        tiempos = [t for t in (self.t_imu['delantera'], self.t_imu['trasera'], self.t_bateria)
                   if t is not None]
        if not tiempos:
            return
        conectado = ahora - max(tiempos) < self.timeout_firmware
        if conectado != self.firmware_ok:
            if conectado:
                self.notificar(INFO, 'firmware', 'FIRMWARE_CONECTADO',
                               'Llegan datos del firmware.')
            else:
                self.notificar(ALERTA, 'firmware', 'FIRMWARE_SIN_DATOS',
                               'Sin datos del firmware por más de 1 s: '
                               'probablemente se perdió la conexión. '
                               'Si el firmware deja de recibir el heartbeat, entra en modo seguro '
                               '(tracción 0 y, si no está en el suelo, succión al máximo).')
            self.firmware_ok = conectado

    def actualizar_estado(self):
        inc = [i for m, i in self.inclinacion.items() if i is not None and self.imu_ok[m]]
        if len(inc) < 2:
            return  # sin las dos IMUs se mantiene el último estado conocido
        if self.estado is None:
            nuevo = ('SUELO' if max(inc) < self.umbral_suelo
                     else 'PARED' if min(inc) > self.umbral_pared else 'TRANSICION')
        elif max(inc) < self.umbral_suelo - 5:
            nuevo = 'SUELO'
        elif min(inc) > self.umbral_pared + 5:
            nuevo = 'PARED'
        elif max(inc) > self.umbral_suelo + 5 and self.estado == 'SUELO':
            nuevo = 'TRANSICION'
        elif min(inc) < self.umbral_pared - 5 and self.estado == 'PARED':
            nuevo = 'TRANSICION'
        else:
            nuevo = self.estado
        if nuevo != self.estado:
            self.estado = nuevo
            textos = {'SUELO': 'El robot está en el suelo.',
                      'TRANSICION': 'El robot está pasando entre suelo y pared: '
                                    'velocidad reducida y succión mínima.',
                      'PARED': 'El robot está en la pared: succión mínima garantizada.'}
            self.notificar(INFO, 'supervisor', f'ESTADO_{nuevo}', textos[nuevo])
            if nuevo != 'SUELO' and self.prueba:
                self.prueba = False
                self.notificar(AVISO, 'supervisor', 'MODO_PRUEBA_OFF',
                               'Modo prueba desactivado: el robot dejó el suelo.')


def main(args=None):
    rclpy.init(args=args)
    node = StateMachineNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
