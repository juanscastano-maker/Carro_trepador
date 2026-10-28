"""Pruebas unitarias del estimador de postura (joint_state_estimator_node)."""

import math

import pytest

from carro_trepador_control.joint_state_estimator_node import cuaternion_rpy


def test_sin_giro_es_la_identidad():
    assert cuaternion_rpy(0.0, 0.0, 0.0) == pytest.approx((0.0, 0.0, 0.0, 1.0))


def test_cabeceo_puro():
    x, y, z, w = cuaternion_rpy(0.0, math.radians(90), 0.0)
    assert (x, z) == pytest.approx((0.0, 0.0))
    assert (y, w) == pytest.approx((math.sin(math.pi / 4), math.cos(math.pi / 4)))


def test_cuaternion_unitario():
    q = cuaternion_rpy(0.3, -1.2, 2.0)
    assert sum(c * c for c in q) == pytest.approx(1.0)
