"""Pruebas unitarias de la cinemática diferencial (kinematics_node.velocidades_rueda)."""

import pytest

from carro_trepador_control.kinematics_node import velocidades_rueda

SEPARACION = 0.1658
V_MAX = 0.47


def test_quieto():
    assert velocidades_rueda(0.0, 0.0, SEPARACION, V_MAX) == (0.0, 0.0)


def test_recto_adelante_y_atras():
    izq, der = velocidades_rueda(0.235, 0.0, SEPARACION, V_MAX)
    assert izq == pytest.approx(0.5)
    assert der == pytest.approx(0.5)
    izq, der = velocidades_rueda(-0.235, 0.0, SEPARACION, V_MAX)
    assert izq == pytest.approx(-0.5)
    assert der == pytest.approx(-0.5)


def test_giro_en_el_sitio_a_la_izquierda():
    # Angular positiva = giro a la izquierda: la rueda derecha avanza y la izquierda retrocede
    izq, der = velocidades_rueda(0.0, 1.0, SEPARACION, V_MAX)
    assert izq < 0 < der
    assert izq == pytest.approx(-der)


def test_saturacion_conserva_la_curvatura():
    # Pedir más de lo que pueden dar las ruedas: ninguna pasa de 1 y la proporción se mantiene
    izq, der = velocidades_rueda(1.0, 2.0, SEPARACION, V_MAX)
    assert max(abs(izq), abs(der)) == pytest.approx(1.0)
    izq_sin, der_sin = (1.0 - 2.0 * SEPARACION / 2), (1.0 + 2.0 * SEPARACION / 2)
    assert izq / der == pytest.approx(izq_sin / der_sin)
