"""
Interfaz del operador del robot trepador (custom_gui_node).

Ver docs/arquitectura/Arquitectura_Carro_trepador_v5.docx. La GUI no manda órdenes directas a los
motores: pide movimiento (/cmd_vel) y succión (/suction_gui_request) al supervisor. Lo único que
manda directo al firmware es la parada de emergencia (/e_stop), que solo decide el operador.

Publica:  /cmd_vel (10 Hz, en cero si no se mueve nada), /suction_gui_request, /e_stop
Recibe:   /gui/notifications, /battery/state, video HTTP MJPEG de la ESP32
Servicio: /set_test_mode (cliente)

Teclado: W/S o flechas arriba/abajo = avanzar/retroceder, A/D o flechas = girar,
         Espacio = PARADA DE EMERGENCIA.

Parámetros: url_video (p. ej. http://192.168.1.50:81/stream), velocidad_lineal_max,
velocidad_angular_max.
"""

import math
import sys
import threading
import time
import urllib.request

from carro_trepador_interfaces.msg import Notificacion
from geometry_msgs.msg import Twist
from PyQt5.QtCore import QEvent, QObject, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QApplication, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QMainWindow, QPushButton, QSlider, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data, ReliabilityPolicy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, Float32
from std_srvs.srv import SetBool

QOS_NOTIFICACIONES = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
QOS_CONFIABLE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

NIVELES = {Notificacion.INFO: ('INFO', '#546E7A', '#FFFFFF'),
           Notificacion.AVISO: ('AVISO', '#8D6E00', '#FFF8E1'),
           Notificacion.ALERTA: ('ALERTA', '#B71C1C', '#FFEBEE')}
ESTADOS = {'SUELO': ('#2E7D32', 'EN EL SUELO'), 'TRANSICION': ('#EF6C00', 'TRANSICIÓN'),
           'PARED': ('#1565C0', 'EN LA PARED'), None: ('#78909C', 'ESTADO DESCONOCIDO')}


# ============================================================================ batería
class IndicadorBateria(QWidget):
    """Batería como la de un celular: relleno, porcentaje y color."""

    def __init__(self):
        super().__init__()
        self.porcentaje = None  # None = sin dato
        self.texto_sin_dato = 'Sin conexión'
        self.setMinimumSize(150, 54)

    def actualizar(self, porcentaje, texto_sin_dato='Sin conexión'):
        self.porcentaje = porcentaje
        self.texto_sin_dato = texto_sin_dato
        self.update()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width() - 14, self.height() - 8
        cuerpo = QRectF(2, 4, w, h)
        if self.porcentaje is None:
            color = QColor('#9E9E9E')
        elif self.porcentaje > 0.5:
            color = QColor('#2E7D32')
        elif self.porcentaje > 0.2:
            color = QColor('#F9A825')
        else:
            color = QColor('#C62828')
        p.setPen(QPen(QColor('#37474F'), 2))
        p.drawRoundedRect(cuerpo, 6, 6)
        p.setBrush(QColor('#37474F'))
        p.drawRoundedRect(QRectF(w + 3, 4 + h * 0.3, 8, h * 0.4), 2, 2)
        if self.porcentaje is not None:
            relleno = QRectF(5, 7, max(0.0, (w - 6) * min(1.0, self.porcentaje)), h - 6)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(relleno, 4, 4)
        # Texto blanco solo cuando el relleno verde cubre el centro; si no, oscuro para que se lea
        p.setPen(QColor('#FFFFFF') if self.porcentaje and self.porcentaje > 0.5
                 else QColor('#263238'))
        f = QFont()
        f.setBold(True)
        f.setPointSize(13)
        p.setFont(f)
        if self.porcentaje is None:
            texto = self.texto_sin_dato
        else:
            texto = f'{self.porcentaje * 100:.0f} %'
        p.drawText(cuerpo, Qt.AlignCenter, texto)


# ============================================================================ video
class LectorVideo(QObject):
    """Lee el video MJPEG de la ESP32 en un hilo aparte y entrega cada cuadro como QImage."""

    cuadro = pyqtSignal(QImage)
    estado = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.activo = True
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        while self.activo:
            try:
                self.estado.emit(f'Conectando a {self.url} ...')
                with urllib.request.urlopen(self.url, timeout=3) as resp:
                    buffer = b''
                    while self.activo:
                        datos = resp.read(4096)
                        if not datos:
                            break
                        buffer += datos
                        inicio = buffer.find(b'\xff\xd8')
                        fin = buffer.find(b'\xff\xd9', inicio + 2)
                        if inicio != -1 and fin != -1:
                            jpg, buffer = buffer[inicio:fin + 2], buffer[fin + 2:]
                            img = QImage.fromData(jpg, 'JPG')
                            if not img.isNull():
                                self.cuadro.emit(img)
                        elif len(buffer) > 2_000_000:
                            buffer = b''
            except Exception as e:  # noqa: BLE001 - cualquier error de red: reintentar
                self.estado.emit(f'Sin video ({type(e).__name__}). Reintentando...')
                time.sleep(3)

    def detener(self):
        self.activo = False


# ============================================================================ nodo ROS
class NodoGui(Node):
    def __init__(self):
        super().__init__('custom_gui_node')
        self.url_video = self.declare_parameter('url_video', '').value
        self.v_max = self.declare_parameter('velocidad_lineal_max', 0.25).value
        self.w_max = self.declare_parameter('velocidad_angular_max', 1.5).value
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_succion = self.create_publisher(Float32, '/suction_gui_request', 10)
        self.pub_e_stop = self.create_publisher(Bool, '/e_stop', QOS_CONFIABLE)
        self.cliente_prueba = self.create_client(SetBool, '/set_test_mode')
        self.notificaciones = []
        self.bateria = None
        self.t_bateria = None
        self.create_subscription(Notificacion, '/gui/notifications', self._al_notificacion,
                                 QOS_NOTIFICACIONES)
        self.create_subscription(BatteryState, '/battery/state', self._al_bateria,
                                 qos_profile_sensor_data)

    def _al_notificacion(self, msg):
        self.notificaciones.append(msg)

    def tomar_notificaciones(self):
        pendientes, self.notificaciones = self.notificaciones, []
        return pendientes

    def _al_bateria(self, msg):
        self.bateria = msg
        self.t_bateria = time.monotonic()


# ============================================================================ ventana
class Ventana(QMainWindow):
    def __init__(self, nodo):
        super().__init__()
        self.nodo = nodo
        self.setWindowTitle('Carro Trepador — Interfaz del operador')
        self.resize(1280, 820)
        self.teclas = set()
        self.botones_mov = {'adelante': False, 'atras': False, 'izq': False, 'der': False}
        self.parada = False
        self.liberando = 0
        self.estado = None
        self.prueba = False
        self.corrientes = []
        self._armar()

        self.timer_ros = QTimer(self, timeout=self._girar_ros)
        self.timer_ros.start(10)
        self.timer_cmd = QTimer(self, timeout=self._publicar_cmd)
        self.timer_cmd.start(100)
        self.timer_e_stop = QTimer(self, timeout=self._publicar_e_stop)
        self.timer_e_stop.start(250)
        self.timer_ui = QTimer(self, timeout=self._refrescar)
        self.timer_ui.start(200)

        self.video = None
        if nodo.url_video:
            self.video = LectorVideo(nodo.url_video)
            self.video.cuadro.connect(self._mostrar_cuadro)
            self.video.estado.connect(self.lbl_video.setText)
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------------ armado
    def _armar(self):
        central = QWidget()
        raiz = QVBoxLayout(central)

        # Barra superior: estado, conexión y batería
        barra = QHBoxLayout()
        self.lbl_estado = QLabel()
        self.lbl_estado.setAlignment(Qt.AlignCenter)
        self.lbl_estado.setMinimumWidth(260)
        self.lbl_modo = QLabel()
        self.lbl_conexion = QLabel()
        self.bateria = IndicadorBateria()
        self.lbl_bateria = QLabel('—')
        self.lbl_bateria.setStyleSheet('color:#37474F')
        barra.addWidget(self.lbl_estado)
        barra.addWidget(self.lbl_modo)
        barra.addStretch()
        barra.addWidget(self.lbl_conexion)
        barra.addSpacing(16)
        barra.addWidget(self.lbl_bateria)
        barra.addWidget(self.bateria)
        raiz.addLayout(barra)

        medio = QHBoxLayout()
        # Video
        caja_video = QGroupBox('Cámara')
        lv = QVBoxLayout(caja_video)
        self.lbl_video = QLabel('Video no configurado (parámetro url_video).')
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setMinimumSize(480, 320)
        self.lbl_video.setStyleSheet('background:#111; color:#B0BEC5; border-radius:6px')
        lv.addWidget(self.lbl_video)
        medio.addWidget(caja_video, 3)

        # Controles
        controles = QVBoxLayout()
        caja_mov = QGroupBox('Movimiento (teclado: W A S D o flechas)')
        g = QGridLayout(caja_mov)
        estilo_flecha = 'font-size:22px; min-height:48px; min-width:64px'
        for texto, clave, fila, col in [('▲', 'adelante', 0, 1), ('◀', 'izq', 1, 0),
                                        ('▼', 'atras', 1, 1), ('▶', 'der', 1, 2)]:
            b = QPushButton(texto)
            b.setStyleSheet(estilo_flecha)
            b.setFocusPolicy(Qt.NoFocus)
            b.pressed.connect(lambda c=clave: self._boton_mov(c, True))
            b.released.connect(lambda c=clave: self._boton_mov(c, False))
            g.addWidget(b, fila, col)
        self.sld_velocidad = QSlider(Qt.Horizontal, minimum=10, maximum=100, value=50)
        self.lbl_velocidad = QLabel()
        self.sld_velocidad.valueChanged.connect(
            lambda v: self.lbl_velocidad.setText(f'Velocidad: {v} %'))
        self.sld_velocidad.setValue(40)
        g.addWidget(self.lbl_velocidad, 2, 0, 1, 3)
        g.addWidget(self.sld_velocidad, 3, 0, 1, 3)
        self.lbl_orden = QLabel('Orden: detenido')
        self.lbl_orden.setStyleSheet('color:#546E7A')
        g.addWidget(self.lbl_orden, 4, 0, 1, 3)
        controles.addWidget(caja_mov)

        caja_suc = QGroupBox('Succión')
        ls = QVBoxLayout(caja_suc)
        self.sld_succion = QSlider(Qt.Horizontal, minimum=0, maximum=100, value=0)
        self.lbl_succion = QLabel('Succión pedida: 0 %')
        self.sld_succion.valueChanged.connect(
            lambda v: self.lbl_succion.setText(f'Succión pedida: {v} %'))
        b_suc = QPushButton('Pedir succión al supervisor')
        b_suc.clicked.connect(self._pedir_succion)
        ls.addWidget(self.lbl_succion)
        ls.addWidget(self.sld_succion)
        ls.addWidget(b_suc)
        controles.addWidget(caja_suc)

        self.btn_prueba = QPushButton('Activar modo prueba')
        self.btn_prueba.clicked.connect(self._alternar_prueba)
        controles.addWidget(self.btn_prueba)

        self.btn_parada = QPushButton('PARADA DE EMERGENCIA\n(Espacio)')
        self.btn_parada.setStyleSheet('background:#C62828; color:white; font-size:20px; '
                                      'font-weight:bold;'
                                      'min-height:80px; border-radius:8px')
        self.btn_parada.setFocusPolicy(Qt.NoFocus)
        self.btn_parada.clicked.connect(self._activar_parada)
        self.btn_liberar = QPushButton('Liberar parada')
        self.btn_liberar.setStyleSheet('min-height:36px; font-size:14px')
        self.btn_liberar.clicked.connect(self._liberar_parada)
        controles.addWidget(self.btn_parada)
        controles.addWidget(self.btn_liberar)
        controles.addStretch()
        medio.addLayout(controles, 2)
        raiz.addLayout(medio, 3)

        # Notificaciones
        caja_not = QGroupBox('Notificaciones del robot')
        ln = QVBoxLayout(caja_not)
        fila_filtro = QHBoxLayout()
        fila_filtro.addWidget(QLabel('Mostrar:'))
        self.cmb_filtro = QComboBox()
        self.cmb_filtro.addItems(['Todas', 'Avisos y alertas', 'Solo alertas'])
        self.cmb_filtro.currentIndexChanged.connect(self._refiltrar)
        fila_filtro.addWidget(self.cmb_filtro)
        fila_filtro.addStretch()
        ln.addLayout(fila_filtro)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(['Hora', 'Nivel', 'Origen', 'Mensaje'])
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.NoSelection)
        self.tabla.setFocusPolicy(Qt.NoFocus)
        ln.addWidget(self.tabla)
        raiz.addWidget(caja_not, 3)

        self.setCentralWidget(central)
        self.statusBar().showMessage('Listo.')

    # ------------------------------------------------------------------ teclado
    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.KeyPress, QEvent.KeyRelease) and not ev.isAutoRepeat():
            tecla = ev.key()
            if tecla == Qt.Key_Space and ev.type() == QEvent.KeyPress:
                self._activar_parada()
                return True
            if tecla in (Qt.Key_W, Qt.Key_S, Qt.Key_A, Qt.Key_D,
                         Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                (self.teclas.add if ev.type() == QEvent.KeyPress else self.teclas.discard)(tecla)
                return True
        return super().eventFilter(obj, ev)

    def _boton_mov(self, clave, presionado):
        self.botones_mov[clave] = presionado

    def _orden_actual(self):
        k, b = self.teclas, self.botones_mov
        adelante = b['adelante'] or Qt.Key_W in k or Qt.Key_Up in k
        atras = b['atras'] or Qt.Key_S in k or Qt.Key_Down in k
        izq = b['izq'] or Qt.Key_A in k or Qt.Key_Left in k
        der = b['der'] or Qt.Key_D in k or Qt.Key_Right in k
        f = self.sld_velocidad.value() / 100.0
        v = (adelante - atras) * self.nodo.v_max * f
        w = (izq - der) * self.nodo.w_max * f
        return v, w

    # ------------------------------------------------------------------ publicaciones
    def _publicar_cmd(self):
        v, w = self._orden_actual()
        msg = Twist()
        msg.linear.x, msg.angular.z = float(v), float(w)
        # siempre, aunque sea cero: el supervisor sabe que la GUI vive
        self.nodo.pub_cmd.publish(msg)
        self.lbl_orden.setText('Orden: detenido' if v == 0 and w == 0
                               else f'Orden: {v:+.2f} m/s, {w:+.2f} rad/s')

    def _activar_parada(self):
        if not self.parada:
            self.parada = True
            self.statusBar().showMessage('PARADA DE EMERGENCIA activada.')
        self._publicar_e_stop()

    def _liberar_parada(self):
        if not self.parada:
            return
        v, w = self._orden_actual()
        if v != 0 or w != 0:
            self.statusBar().showMessage(
                'Suelta los controles de movimiento antes de liberar la parada.')
            return
        self.parada = False
        self.liberando = 4  # se publica False varias veces por si se pierde un mensaje
        self.statusBar().showMessage('Parada liberada.')

    def _publicar_e_stop(self):
        if self.parada:
            self.nodo.pub_e_stop.publish(Bool(data=True))
        elif self.liberando > 0:
            self.liberando -= 1
            self.nodo.pub_e_stop.publish(Bool(data=False))

    def _pedir_succion(self):
        self.nodo.pub_succion.publish(Float32(data=float(self.sld_succion.value())))

    def _alternar_prueba(self):
        if not self.nodo.cliente_prueba.service_is_ready():
            self.statusBar().showMessage('El supervisor no responde (servicio /set_test_mode).')
            return
        futuro = self.nodo.cliente_prueba.call_async(SetBool.Request(data=not self.prueba))
        futuro.add_done_callback(lambda f: self.statusBar().showMessage(f.result().message))

    # ------------------------------------------------------------------ actualización
    def _girar_ros(self):
        rclpy.spin_once(self.nodo, timeout_sec=0)

    def _mostrar_cuadro(self, img):
        self.lbl_video.setPixmap(QPixmap.fromImage(img).scaled(
            self.lbl_video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _refrescar(self):
        # Notificaciones nuevas
        for n in self.nodo.tomar_notificaciones():
            self._procesar_notificacion(n)
            self._agregar_fila(n)

        # Estado del robot
        color, texto = ESTADOS.get(self.estado, ESTADOS[None])
        if self.parada:
            color, texto = '#B71C1C', 'PARADA DE EMERGENCIA'
        self.lbl_estado.setText(texto)
        self.lbl_estado.setStyleSheet(f'background:{color}; color:white; font-size:18px; '
                                      'font-weight:bold;'
                                      'padding:8px 16px; border-radius:8px')
        self.lbl_modo.setText('MODO PRUEBA' if self.prueba else '')
        self.lbl_modo.setStyleSheet('background:#6A1B9A; color:white; font-weight:bold; '
                                    'padding:6px 10px;'
                                    'border-radius:6px' if self.prueba else '')
        self.btn_prueba.setText('Desactivar modo prueba' if self.prueba else 'Activar modo prueba')
        v, w = self._orden_actual()
        self.btn_liberar.setEnabled(self.parada and v == 0 and w == 0)

        # Batería y conexión (si la batería no llega en 1 s, se perdió la conexión con el robot)
        b, t = self.nodo.bateria, self.nodo.t_bateria
        conectado = t is not None and time.monotonic() - t < 1.0
        if conectado and (not b.present or math.isnan(b.voltage)):
            # El firmware está conectado pero el INA226 no responde
            self.bateria.actualizar(None, 'Sin medición')
            self.lbl_bateria.setText('INA226 sin datos')
            self.lbl_conexion.setText('● Robot conectado')
            self.lbl_conexion.setStyleSheet('color:#2E7D32; font-weight:bold')
        elif conectado:
            self.bateria.actualizar(b.percentage)
            corriente = -b.current
            self.corrientes = (self.corrientes + [corriente])[-50:]
            media = sum(self.corrientes) / len(self.corrientes)
            celda = b.voltage / 4
            minutos = b.charge / media * 60 if media > 0.05 else float('inf')
            resto = '' if minutos == float('inf') else f' · ~{minutos:.0f} min'
            self.lbl_bateria.setText(
                f'{b.voltage:.2f} V ({celda:.2f} V/celda) · {corriente:.1f} A{resto}')
            self.lbl_conexion.setText('● Robot conectado')
            self.lbl_conexion.setStyleSheet('color:#2E7D32; font-weight:bold')
        else:
            self.bateria.actualizar(None)
            self.lbl_bateria.setText('—')
            self.lbl_conexion.setText('● Sin conexión con el robot')
            self.lbl_conexion.setStyleSheet('color:#C62828; font-weight:bold')

    def _procesar_notificacion(self, n):
        c = n.codigo
        if c.startswith('ESTADO_'):
            self.estado = c[len('ESTADO_'):]
        elif c == 'MODO_PRUEBA_ON':
            self.prueba = True
        elif c == 'MODO_PRUEBA_OFF':
            self.prueba = False
        elif c == 'PARADA_ACTIVADA':
            self.parada = True  # también si la GUI se reinició con la parada activa

    def _agregar_fila(self, n):
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        hora = (time.strftime('%H:%M:%S', time.localtime(n.stamp.sec)) if n.stamp.sec
                else '--:--:--')
        nombre, color_txt, fondo = NIVELES.get(n.nivel, NIVELES[Notificacion.INFO])
        for col, valor in enumerate([hora, nombre, n.origen, n.texto]):
            item = QTableWidgetItem(valor)
            item.setBackground(QColor(fondo))
            item.setForeground(QColor(color_txt if col == 1 else '#263238'))
            if col == 1:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self.tabla.setItem(fila, col, item)
        self.tabla.setRowHidden(fila, not self._visible(n.nivel))
        self.tabla.scrollToBottom()

    def _visible(self, nivel):
        minimo = self.cmb_filtro.currentIndex()  # 0 todas, 1 avisos y alertas, 2 solo alertas
        return nivel >= minimo

    def _refiltrar(self):
        orden = {'INFO': 0, 'AVISO': 1, 'ALERTA': 2}
        for fila in range(self.tabla.rowCount()):
            nivel = orden.get(self.tabla.item(fila, 1).text(), 0)
            self.tabla.setRowHidden(fila, not self._visible(nivel))

    def closeEvent(self, ev):
        if self.video:
            self.video.detener()
        super().closeEvent(ev)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoGui()
    app = QApplication(sys.argv)
    ventana = Ventana(nodo)
    ventana.show()
    try:
        app.exec_()
    finally:
        nodo.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
