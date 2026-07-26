# A13 — menor distância imóvel → feição externa (`geo/distancia.py`).

from __future__ import annotations

import pytest
from shapely.geometry import Point, box

from mapasfacil_nucleo.geo.distancia import distancia_minima_km


def test_distancia_minima_km_em_utm_e_exata() -> None:
    referencia = box(500_000, 8_000_000, 500_100, 8_000_100)  # UTM — 100 m de lado
    alvo = box(501_000, 8_000_000, 501_100, 8_000_100)  # 900 m a leste da borda
    distancia = distancia_minima_km(referencia, 31982, [alvo], 31982)
    assert distancia == pytest.approx(0.9, abs=0.001)


def test_distancia_minima_km_sem_alvos_e_none() -> None:
    referencia = box(0, 0, 1, 1)
    assert distancia_minima_km(referencia, 31982, [], 31982) is None


def test_distancia_minima_km_reprojeta_epsg_diferentes() -> None:
    # Referência em geográfico (4674), alvo já em UTM — função tem de casar os dois.
    referencia = Point(-58.0, -11.0).buffer(0.001)
    alvo = box(500_000, 8_500_000, 500_100, 8_500_100)
    distancia = distancia_minima_km(referencia, 4674, [alvo], 31982)
    assert distancia is not None
    assert distancia > 0


def test_distancia_minima_km_geometrias_sobrepostas_e_zero() -> None:
    referencia = box(500_000, 8_000_000, 500_200, 8_000_200)
    alvo = box(500_100, 8_000_100, 500_300, 8_000_300)  # sobrepõe a referência
    assert distancia_minima_km(referencia, 31982, [alvo], 31982) == 0.0
