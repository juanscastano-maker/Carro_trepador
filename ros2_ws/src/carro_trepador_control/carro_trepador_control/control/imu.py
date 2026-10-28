"""
Cálculos de orientación a partir de sensor_msgs/Imu, compartidos por los nodos de control.

Si el mensaje trae orientación (el firmware la calcula con un filtro), se usa esa. Si no la trae
(orientation_covariance[0] == -1, convención de ROS), se estima con el acelerómetro, que vale
mientras el robot no acelere fuerte.

Ejes del módulo (REP-103): x hacia adelante, y a la izquierda, z hacia arriba.
"""

import math


def _tiene_orientacion(msg):
    q = msg.orientation
    return msg.orientation_covariance[0] != -1.0 and (q.w or q.x or q.y or q.z)


def inclinacion(msg):
    """
    Ángulo entre el eje z del módulo y la vertical, en grados.

    0 = plano en el suelo, 90 = sobre una pared vertical, 180 = boca abajo (techo).
    No depende de hacia dónde apunte el robot sobre la pared.
    """
    if _tiene_orientacion(msg):
        q = msg.orientation
        cos_t = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
    else:
        a = msg.linear_acceleration
        norma = math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z)
        if norma < 1e-3:
            return None
        cos_t = a.z / norma
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_t))))


def cabeceo(msg):
    """Cabeceo en grados: positivo con la nariz del módulo hacia arriba."""
    if _tiene_orientacion(msg):
        q = msg.orientation
        s = 2.0 * (q.w * q.y - q.z * q.x)
        # En ROS, el giro positivo alrededor de y baja la nariz: se cambia el signo
        return -math.degrees(math.asin(max(-1.0, min(1.0, s))))
    a = msg.linear_acceleration
    return math.degrees(math.atan2(a.x, math.sqrt(a.y * a.y + a.z * a.z)))


def alabeo(msg):
    """Alabeo en grados: positivo con el lado izquierdo hacia arriba."""
    if _tiene_orientacion(msg):
        q = msg.orientation
        return math.degrees(math.atan2(2.0 * (q.w * q.x + q.y * q.z),
                                       1.0 - 2.0 * (q.x * q.x + q.y * q.y)))
    a = msg.linear_acceleration
    return math.degrees(math.atan2(a.y, a.z))
