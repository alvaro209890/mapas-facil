# A13 — cliente HTTP de camadas (`camadas/http.py`): redator de URL, retry/timeout.

from __future__ import annotations

import pytest

from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.erros import ErroNucleo


@pytest.fixture(autouse=True)
def _sem_transporte_real():
    yield
    http.configurar_transporte(None)


def test_redigir_url_mascara_authkey_e_api_key() -> None:
    url = "https://geo.sema.mt.gov.br/geoserver/ows?authkey=segredo-super-secreto&bbox=1,2,3,4"
    redigida = http.redigir_url(url)
    assert "segredo-super-secreto" not in redigida
    assert "authkey=%2A%2A%2A" in redigida or "authkey=***" in redigida
    assert "bbox=1%2C2%2C3%2C4" in redigida or "bbox=1,2,3,4" in redigida


def test_redigir_url_mascara_api_key_e_token() -> None:
    url = "https://tiles.planet.com/x?api_key=chave123&token=outro456&z=1"
    redigida = http.redigir_url(url)
    assert "chave123" not in redigida
    assert "outro456" not in redigida


def test_redigir_url_preserva_parametros_normais() -> None:
    url = "https://x.example/ows?service=WFS&count=2000"
    assert http.redigir_url(url) == url


def test_buscar_usa_transporte_injetado() -> None:
    chamadas = []

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        chamadas.append(url)
        return http.RespostaHttp(status=200, corpo=b'{"ok":true}', content_type="application/json")

    http.configurar_transporte(fake)
    resp = http.buscar("https://x.example/ows")
    assert resp.status == 200
    assert len(chamadas) == 1


def test_buscar_repete_e_desiste_apos_as_tentativas() -> None:
    chamadas = []

    def fake_falha(url: str, timeout: int) -> http.RespostaHttp:
        chamadas.append(url)
        raise ErroNucleo("NU-101", "timeout simulado")

    http.configurar_transporte(fake_falha)
    with pytest.raises(ErroNucleo) as exc:
        http.buscar("https://x.example/ows", tentativas=2, dormir=lambda _s: None)
    assert exc.value.codigo == "NU-101"
    assert len(chamadas) == 3  # tentativa inicial + 2 retries


def test_buscar_recupera_apos_falha_transitoria() -> None:
    estado = {"tentativa": 0}

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        estado["tentativa"] += 1
        if estado["tentativa"] < 2:
            raise ErroNucleo("NU-101", "timeout simulado")
        return http.RespostaHttp(status=200, corpo=b"{}", content_type="application/json")

    http.configurar_transporte(fake)
    resp = http.buscar("https://x.example/ows", tentativas=2, dormir=lambda _s: None)
    assert resp.status == 200
    assert estado["tentativa"] == 2
