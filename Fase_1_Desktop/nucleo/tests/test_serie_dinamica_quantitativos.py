# Testes dos quantitativos da série Dinâmica (W11-11).

import pytest
from shapely.geometry import box
from mapasfacil_nucleo.analise.serie import (
    MARCOS_QUANTITATIVOS,
    calcular_quantitativos_dinamica,
)


def test_marcos_quantitativos_estritos() -> None:
    """W11-11: só três marcos levam quantitativo (2000, 2008 e o ano atual)."""
    assert list(MARCOS_QUANTITATIVOS) == [2000, 2008, 2026]


def test_calcular_quantitativos_dinamica_avn_e_desmate() -> None:
    """W11-11: AVN = AIR - AC - agua; desmate pos-2008 = AC + AUAS (autorizado x nao autorizado)."""
    # Imóvel: 1000m x 1000m = 1.000.000 m² = 100 ha
    imovel = box(500_000, 8_000_000, 501_000, 8_001_000)

    # AC: 300m x 1000m = 300.000 m² = 30 ha
    ac = box(500_000, 8_000_000, 500_300, 8_001_000)

    # Água: 100m x 1000m = 100.000 m² = 10 ha
    agua = box(500_300, 8_000_000, 500_400, 8_001_000)

    # AUAS: 100m x 1000m = 100.000 m² = 10 ha (adicional ao AC)
    auas = box(500_400, 8_000_000, 500_500, 8_001_000)

    # AEF (autorização): cobre metade do AC (15 ha)
    aef = box(500_000, 8_000_000, 500_150, 8_001_000)

    res = calcular_quantitativos_dinamica(
        geom_imovel=imovel,
        geom_ac=ac,
        geom_agua=agua,
        geom_auas=auas,
        geoms_aef=[aef],
    )

    assert res["area_imovel_ha"] == 100.0
    assert res["ac_ha"] == 30.0
    assert res["agua_ha"] == 10.0
    # AVN = 100 - 30 (AC) - 10 (Água) = 60 ha
    assert res["avn_ha"] == 60.0
    assert res["auas_ha"] == 10.0
    # Desmate pós-2008 = AC (30 ha) + AUAS (10 ha) = 40 ha
    assert res["desmate_pos_2008_ha"] == 40.0
    # Autorizado por AEF = 15 ha
    assert res["desmate_autorizado_ha"] == 15.0
    # Não autorizado = 40 - 15 = 25 ha
    assert res["desmate_nao_autorizado_ha"] == 25.0


def test_descarte_de_lascas_menores_que_100m2() -> None:
    """W11-11: lascas < 100 m² na divisa são descartadas."""
    # Imóvel: 100m x 100m = 10.000 m² = 1 ha
    imovel = box(500_000, 8_000_000, 500_100, 8_000_100)
    # AC cobre tudo menos uma fresta de 10m x 5m = 50 m² (< 100 m²)
    # Criamos AC cortando o imóvel menos essa lasca
    lasca = box(500_000, 8_000_000, 500_010, 8_000_005)
    ac = imovel.difference(lasca)

    res = calcular_quantitativos_dinamica(
        geom_imovel=imovel,
        geom_ac=ac,
        limiar_lasca_m2=100.0,
    )
    # A lasca de 50 m² foi descartada (< 100 m² = 0.01 ha)
    assert res["avn_ha"] == 0.0
