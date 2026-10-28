"""Pruebas unitarias de la succión automática (suction_control_node.succion_automatica)."""

import pytest

from carro_trepador_control.suction_control_node import succion_automatica


def calcular(angulo):
    return succion_automatica(angulo, umbral_suelo=25.0, umbral_pared=65.0, succion_suelo=0.0,
                              succion_pared=70.0)


@pytest.mark.parametrize('angulo, esperado', [
    (0.0, 0.0),     # plano en el suelo
    (25.0, 0.0),    # justo en el umbral del suelo
    (45.0, 35.0),   # a mitad de camino
    (65.0, 70.0),   # justo en el umbral de la pared
    (90.0, 70.0),   # pared vertical
    (150.0, 70.0),  # más allá de la pared (hacia el techo)
])
def test_succion_segun_inclinacion(angulo, esperado):
    assert calcular(angulo) == pytest.approx(esperado)


def test_nunca_baja_al_inclinarse_mas():
    valores = [calcular(a) for a in range(0, 100, 5)]
    assert valores == sorted(valores)
