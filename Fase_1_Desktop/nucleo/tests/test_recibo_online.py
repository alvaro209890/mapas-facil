# Recibo do CAR buscado na SEMA quando o .zip do usuário não traz (pedido do Álvaro, 04/11/2026).
# Sem rede: o transporte HTTP é trocado por um dublê que responde como a SEMA respondeu ao vivo.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo import cofre
from mapasfacil_nucleo.agente.tools import executar
from mapasfacil_nucleo.workspace import recibo_online
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_geografico


class SemaFalsa:
    """Responde WFS, ListarRequerimento e DownloadReciboCar como a SEMA real."""

    def __init__(self, pdf: bytes, *, car: str = "MT96184/2020", tem_car: bool = True) -> None:
        self.pdf = pdf
        self.car = car
        self.tem_car = tem_car
        self.urls: list[str] = []

    def __call__(self, url: str, corpo: bytes | None, cabecalhos: dict[str, str], timeout: float) -> bytes:
        self.urls.append(url)
        if "geoserver" in url:
            assert "authkey=chave-teste" in url
            feicoes = (
                [{"properties": {"NUMERO": self.car, "CODIGO_CAR": "MT-5107065-X", "AREA_HA": 30.0}}]
                if self.tem_car and "ANALISADO" in url
                else []
            )
            return json.dumps({"features": feicoes}).encode()
        if url.endswith("/Publico/ListarRequerimento"):
            filtros = json.loads(corpo or b"{}")["Filtros"]
            assert set(filtros) == {"NUMERO"}, "chave de filtro desconhecida derruba a SEMA"
            return json.dumps({"Itens": [{"Id": 878064, "NumeroCompleto": filtros["NUMERO"]}]}).encode()
        if "/Publico/DownloadReciboCar/878064" in url:
            return self.pdf
        raise AssertionError(f"URL inesperada: {url}")


@pytest.fixture
def chave_sema():
    mem = cofre.BackendMemoria()
    cofre.configurar_backend(mem)
    cofre.definir("sema_authkey", "chave-teste")
    yield
    cofre.configurar_backend(None)


@pytest.fixture
def pdf_recibo(tmp_path: Path) -> bytes:
    return escrever_recibo_car_pdf(tmp_path / "modelo" / "recibo.pdf").read_bytes()


@pytest.fixture
def pasta_sem_recibo(tmp_path: Path) -> Path:
    pasta = tmp_path / "projeto"
    escrever_shapefile_geografico(pasta / "entrada" / "ATP.shp", lon=-52.25, lat=-12.36, delta=0.005)
    workspace_servico.abrir(str(pasta))
    return pasta


@pytest.fixture(autouse=True)
def _limpar_transporte():
    yield
    recibo_online.configurar_transporte(None)


def test_normalizar_car_aceita_o_que_o_usuario_digita():
    assert recibo_online.normalizar_car("mt 96184-2020") == "MT96184/2020"
    assert recibo_online.normalizar_car("MT96184/2020") == "MT96184/2020"
    assert recibo_online.normalizar_car("96184/2020") is None


def test_sem_recibo_acha_o_car_pelo_perimetro_e_baixa(chave_sema, pdf_recibo, pasta_sem_recibo):
    sema = SemaFalsa(pdf_recibo)
    recibo_online.configurar_transporte(sema)
    assert executar("ler_recibo_car", {}, {})["codigo"] == "NU-042"

    r = executar("buscar_recibo_car", {}, {})
    assert r["ok"] is True, r
    assert r["car"] == "MT96184/2020"
    assert (pasta_sem_recibo / r["arquivo"]).read_bytes()[:5] == b"%PDF-"
    assert r["recibo"]["nome_imovel"] == "Fazenda Harmonia"
    # Depois de baixar, o recibo vale como se tivesse vindo no .zip.
    assert executar("ler_recibo_car", {}, {})["ok"] is True
    # Ponto do WFS em lon lat (é o que a SEMA aceita com EPSG:4674).
    wfs = next(u for u in sema.urls if "geoserver" in u)
    assert "POINT%28-52.2" in wfs


def test_recibo_que_ja_existe_nao_vai_a_sema(chave_sema, tmp_path: Path):
    escrever_shapefile_geografico(tmp_path / "SHP" / "ATP.shp", lon=-52.25, lat=-12.36)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))

    def proibido(*_: Any) -> bytes:
        raise AssertionError("não deveria consultar a SEMA")

    recibo_online.configurar_transporte(proibido)
    r = executar("buscar_recibo_car", {}, {})
    assert r["ok"] is True and r["ja_existia"] is True


def test_car_informado_pelo_usuario_dispensa_o_geoserver(pdf_recibo, pasta_sem_recibo):
    cofre.configurar_backend(cofre.BackendMemoria())  # sem chave: não pode precisar dela
    try:
        sema = SemaFalsa(pdf_recibo)
        recibo_online.configurar_transporte(sema)
        r = executar("buscar_recibo_car", {"car": "mt 96184-2020"}, {})
        assert r["ok"] is True, r
        assert not any("geoserver" in u for u in sema.urls)
    finally:
        cofre.configurar_backend(None)


def test_perimetro_sem_car_na_sema_pede_o_numero(chave_sema, pdf_recibo, pasta_sem_recibo):
    recibo_online.configurar_transporte(SemaFalsa(pdf_recibo, tem_car=False))
    r = executar("buscar_recibo_car", {}, {})
    assert r["ok"] is False and r["codigo"] == "NU-043"


def test_sem_chave_sema_e_sem_numero_pede_o_numero(pdf_recibo, pasta_sem_recibo):
    cofre.configurar_backend(cofre.BackendMemoria())
    try:
        r = executar("buscar_recibo_car", {}, {})
        assert r["ok"] is False and r["codigo"] == "NU-102"
    finally:
        cofre.configurar_backend(None)


def _pdf_car_digital(caminho: Path) -> Path:
    """Layout do recibo atual da SEMA ("CAR Digital"): cabeçalho de rótulos + valores."""
    import pymupdf as fitz

    linhas = [
        "Recibo de Inscrição do CAR Digital",
        "Dados Gerais",
        "Nº CAR Estadual",
        "Situação Estadual",
        "Tipo",
        "MT96184/2020",
        "Ativo",
        "Digital",
        "Dados da Propriedade",
        "Propriedade",
        "UF",
        "Município",
        "LOTE RURAL 43",
        "MT",
        "Querência",
        "Dados das Áreas dos Imóveis Rurais",
        "Documento",
        "Tipo",
        "Área (ha)",
        "Certidão de registro: 1",
        "Matrícula",
        "450,6670",
        "Croqui do CAR",
        "ATP - Área Total da Propriedade",
        "450,6670",
        "APP - Área de Preservação Permanente",
        "28,6234",
    ]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    pagina = doc.new_page()
    for i, linha in enumerate(linhas):
        pagina.insert_text((40, 40 + i * 14), linha, fontsize=9)
    doc.save(caminho)
    doc.close()
    return caminho


def test_parser_le_o_recibo_car_digital(tmp_path: Path):
    from mapasfacil_nucleo.workspace.recibo_car import parsear

    recibo = parsear(_pdf_car_digital(tmp_path / "recibo.pdf")).para_dict()
    assert recibo["nome_imovel"] == "LOTE RURAL 43"
    assert recibo["municipio"] == "Querência"
    assert recibo["uf"] == "MT"
    assert recibo["car_estadual"] == "MT96184/2020"  # 5 dígitos: o regex antigo exigia 6
    assert recibo["situacao"] == "Ativo"
    assert recibo["area_total_ha"] == pytest.approx(450.667)
    assert recibo["areas"]["app_ha"] == pytest.approx(28.6234)
