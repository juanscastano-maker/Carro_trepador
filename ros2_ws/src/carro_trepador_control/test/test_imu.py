"""Pruebas unitarias de los cálculos de orientación (control/imu.py)."""

import math

import pytest
from sensor_msgs.msg import Imu

from carro_trepador_control.control.imu import alabeo, cabeceo, inclinacion

G = 9.80665


def imu_solo_acelerometro(nariz_arriba_grados=0.0, lado_izq_arriba_grados=0.0):
    """IMU sin orientación (covarianza -1): los cálculos usan el acelerómetro."""
    p, r = math.radians(nariz_arriba_grados), math.radians(lado_izq_arriba_grados)
    msg = Imu()
    msg.orientation_covariance[0] = -1.0
    msg.linear_acceleration.x = G * math.sin(p)
    msg.linear_acceleration.y = G * math.cos(p) * math.sin(r)
    msg.linear_acceleration.z = G * math.cos(p) * math.cos(r)
    return msg


def imu_con_cuaternion(nariz_arriba_grados):
    """IMU con orientación ya calculada (como la manda el firmware)."""
    t = math.radians(nariz_arriba_grados)
    msg = Imu()
    # En ROS el cabeceo positivo baja la nariz: nariz arriba = giro negativo alrededor de y
    msg.orientation.w = math.cos(-t / 2)
    msg.orientation.y = math.sin(-t / 2)
    return msg


@pytest.mark.parametrize('crear', [imu_solo_acelerometro, imu_con_cuaternion])
@pytest.mark.parametrize('angulo', [0.0, 30.0, 60.0, 90.0])
def test_inclinacion_y_cabeceo(crear, angulo):
    msg = crear(angulo)
    assert inclinacion(msg) == pytest.approx(angulo, abs=0.01)
    assert cabeceo(msg) == pytest.approx(angulo, abs=0.01)


def test_nariz_abajo_da_cabeceo_negativo():
    assert cabeceo(imu_solo_acelerometro(-20.0)) == pytest.approx(-20.0, abs=0.01)
    assert cabeceo(imu_con_cuaternion(-20.0)) == pytest.approx(-20.0, abs=0.01)


def test_alabeo_e_inclinacion_de_lado():
    msg = imu_solo_acelerometro(lado_izq_arriba_grados=30.0)
    assert alabeo(msg) == pytest.approx(30.0, abs=0.01)
    assert inclinacion(msg) == pytest.approx(30.0, abs=0.01)  # la inclinación no depende del rumbo


def test_sin_datos_no_inventa_un_angulo():
    msg = Imu()
    msg.orientation_covariance[0] = -1.0  # sin orientación y acelerómetro en cero
    assert inclinacion(msg) is None
