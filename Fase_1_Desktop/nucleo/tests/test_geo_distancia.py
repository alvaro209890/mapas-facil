# A13 — menor distância imóvel → feição externa (`geo/distancia.py`).

from __future__ import annotations

import pytest
from shapely.geometry import Point, box

from mapasfacil_nucleo.geo.distancia import avaliar_distancia_ti, distancia_minima_km


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


def test_avaliar_distancia_ti_relatorio_separado() -> None:
    """W11-12: relata TI e zona de amortecimento separadas e sobrepõe como 0."""
    imovel = box(500_000, 8_000_000, 500_100, 8_000_100)

    # 1. TI sobreposta
    ti_sobreposta = box(500_050, 8_000_050, 500_200, 8_000_200)
    r1 = avaliar_distancia_ti(imovel, 31982, [ti_sobreposta], 31982)
    assert r1 is not None
    assert r1.status == "sobrepoe"
    assert r1.distancia_km == 0.0
    assert r1.em_zona_amortecimento is True
    assert "sobrepõe" in r1.mensagem

    # 2. TI a 5 km (dentro da zona de amortecimento de 10 km)
    ti_amortecimento = box(505_100, 8_000_000, 506_000, 8_000_100)
    r2 = avaliar_distancia_ti(imovel, 31982, [ti_amortecimento], 31982, raio_amortecimento_km=10.0)
    assert r2 is not None
    assert r2.status == "zona_amortecimento"
    assert r2.em_zona_amortecimento is True
    assert 4.9 <= r2.distancia_km <= 5.1
    assert "zona de amortecimento" in r2.mensagem

    # 3. TI a 25 km (afastada, fora da zona de amortecimento)
    ti_afastada = box(525_100, 8_000_000, 526_000, 8_000_100)
    r3 = avaliar_distancia_ti(imovel, 31982, [ti_afastada], 31982, raio_amortecimento_km=10.0)
    assert r3 is not None
    assert r3.status == "afastado"
    assert r3.em_zona_amortecimento is False
    assert 24.9 <= r3.distancia_km <= 25.1
    assert "fora da zona de amortecimento" in r3.mensagem
