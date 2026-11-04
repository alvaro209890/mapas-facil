# Testes de metadados automáticos (W11-05) e catálogo de mensagens (W11-07).

import pytest
from mapasfacil_nucleo.motores.metadados import (
    derivar_metadados_mapa,
    formatar_data_mosaico,
    formatar_escala,
    resolver_sensor_padrao,
)
from mapasfacil_nucleo.validacao.mensagens import CATALOGO_CHECKS, obter_mensagem_check


def test_formatar_escala() -> None:
    assert formatar_escala(50000) == "1:50.000"
    assert formatar_escala(125000) == "1:125.000"
    assert formatar_escala(1000000) == "1:1.000.000"


def test_formatar_data_mosaico() -> None:
    assert formatar_data_mosaico("global_monthly_2026_10_mosaic") == "Outubro/2026"
    assert formatar_data_mosaico("planet_2026-07") == "Julho/2026"
    assert formatar_data_mosaico("mosaico_sem_data") == "mosaico_sem_data"


def test_resolver_sensor_padrao() -> None:
    assert resolver_sensor_padrao("planet_scope") == "PLANET"
    assert resolver_sensor_padrao("spot_2008") == "SPOT"
    assert resolver_sensor_padrao("landsat_8") == "LANDSAT 8/OLI"
    assert resolver_sensor_padrao("dinamica_2000") == "LANDSAT 5/TM"


def test_derivar_metadados_mapa() -> None:
    mapspec = {
        "crs": "EPSG:31982",
        "escala": 50000,
        "basemap": {
            "mosaico": "global_monthly_2026_10_mosaic",
            "fonte": "PLANET",
        },
    }
    meta = derivar_metadados_mapa(mapspec)
    rotulos = {m["rotulo"]: m["valor"] for m in meta}

    assert rotulos["Datum"] == "SIRGAS 2000 UTM 22 S"
    assert rotulos["Escala"] == "1:50.000"
    assert rotulos["Satélite/Sensor"] == "PLANET"
    assert rotulos["Data da imagem"] == "Outubro/2026"
    assert rotulos["Fonte"] == "PLANET"


def test_obter_mensagem_check() -> None:
    h18 = obter_mensagem_check("H18")
    assert h18["severidade"] == "hard"
    assert "segredos" in h18["nome"].lower()
    assert "o_que_fazer" in h18

    s21 = obter_mensagem_check("S21")
    assert s21["severidade"] == "soft"
    assert "texto sobre linha" in s21["nome"].lower()

    desconhecido = obter_mensagem_check("XYZ99")
    assert "o_que_fazer" in desconhecido
