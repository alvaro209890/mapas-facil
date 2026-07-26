# A13 — cliente WFS GetFeature (`camadas/wfs.py`) com fixtures gravadas (sem rede).

from __future__ import annotations

from pathlib import Path

import pytest

from mapasfacil_nucleo.camadas import http, wfs
from mapasfacil_nucleo.erros import ErroNucleo

FIXTURES = Path(__file__).parent / "fixtures" / "wfs"

BBOX = (-58.02, -11.02, -57.98, -10.98)
ENDPOINT = "https://geo.sema.mt.gov.br/geoserver/ows"
LAYER = "Geoportal:AREA_EMBARGADA_SIGA_POLIGONO"


@pytest.fixture(autouse=True)
def _sem_transporte_real():
    yield
    http.configurar_transporte(None)


def test_montar_url_getfeature_2_0() -> None:
    url = wfs.montar_url_getfeature(ENDPOINT, LAYER, BBOX, "EPSG:4674", authkey="segredo")
    assert "typeNames=" in url
    assert "version=2.0.0" in url
    assert "srsName=EPSG%3A4674" in url
    assert "authkey=segredo" in url  # a redação é responsabilidade de quem loga, não de quem monta


def test_montar_url_getfeature_1_0_usa_typename_singular() -> None:
    url = wfs.montar_url_getfeature(ENDPOINT, LAYER, BBOX, "EPSG:4674", version="1.0.0")
    assert "typeName=" in url
    assert "typeNames=" not in url
    assert "maxFeatures=" in url
    assert "count=" not in url


def test_buscar_feicoes_parseia_fixture_valida() -> None:
    corpo = (FIXTURES / "embargos_siga_getfeature.json").read_bytes()

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        assert "version=2.0.0" in url
        return http.RespostaHttp(status=200, corpo=corpo, content_type="application/json")

    http.configurar_transporte(fake)
    resultado = wfs.buscar_feicoes(ENDPOINT, LAYER, BBOX, "EPSG:4674", authkey="segredo")
    assert len(resultado["features"]) == 1
    assert resultado["parcial"] is False
    assert resultado["versao_usada"] == "2.0.0"
    assert resultado["total_disponivel"] == 1


def test_buscar_feicoes_vazia_nao_e_erro() -> None:
    corpo = (FIXTURES / "vazio_getfeature.json").read_bytes()
    http.configurar_transporte(
        lambda url, timeout: http.RespostaHttp(status=200, corpo=corpo, content_type="application/json")
    )
    resultado = wfs.buscar_feicoes(ENDPOINT, LAYER, BBOX, "EPSG:4674")
    assert resultado["features"] == []
    assert resultado["parcial"] is False


def test_buscar_feicoes_xml_de_erro_cai_para_1_0_e_falha_com_nu110() -> None:
    xml = (FIXTURES / "erro_geoserver.xml").read_bytes()
    chamadas = []

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        chamadas.append(url)
        return http.RespostaHttp(status=200, corpo=xml, content_type="text/xml")

    http.configurar_transporte(fake)
    with pytest.raises(ErroNucleo) as exc:
        wfs.buscar_feicoes(ENDPOINT, LAYER, BBOX, "EPSG:4674")
    assert exc.value.codigo == "NU-110"
    assert len(chamadas) == 2  # tentou 2.0.0 e caiu para 1.0.0 antes de desistir
    assert "1.0.0" in chamadas[1]


def test_buscar_feicoes_fallback_1_0_funciona_quando_servidor_so_fala_1_0() -> None:
    """Servidor tipo FUNAI: 2.0.0 devolve XML de erro, 1.0.0 devolve JSON válido."""
    xml = (FIXTURES / "erro_geoserver.xml").read_bytes()
    valido = (FIXTURES / "embargos_siga_getfeature.json").read_bytes()

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        if "version=2.0.0" in url:
            return http.RespostaHttp(status=200, corpo=xml, content_type="text/xml")
        return http.RespostaHttp(status=200, corpo=valido, content_type="application/json")

    http.configurar_transporte(fake)
    resultado = wfs.buscar_feicoes(ENDPOINT, LAYER, BBOX, "EPSG:4674")
    assert resultado["versao_usada"] == "1.0.0"
    assert resultado["parcial"] is True
    assert len(resultado["features"]) == 1


def test_buscar_feicoes_timeout_nao_tenta_outra_versao() -> None:
    chamadas = []

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        chamadas.append(url)
        raise ErroNucleo("NU-101", "timeout simulado")

    http.configurar_transporte(fake)
    with pytest.raises(ErroNucleo) as exc:
        wfs.buscar_feicoes(ENDPOINT, LAYER, BBOX, "EPSG:4674", timeout=1)
    assert exc.value.codigo == "NU-101"
    # http.buscar já tenta 2x por padrão; a versão 1.0.0 nunca chega a ser tentada.
    assert all("version=2.0.0" in u for u in chamadas)


def test_buscar_feicoes_status_diferente_de_200_e_nu110() -> None:
    def fake(url: str, timeout: int) -> http.RespostaHttp:
        return http.RespostaHttp(status=500, corpo=b"erro interno", content_type="text/plain")

    http.configurar_transporte(fake)
    with pytest.raises(ErroNucleo) as exc:
        wfs.buscar_feicoes(ENDPOINT, LAYER, BBOX, "EPSG:4674")
    assert exc.value.codigo == "NU-110"
