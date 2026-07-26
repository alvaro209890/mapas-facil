# A13/R21 — `consultar_sema` e `distancia_ate` ligadas de verdade (saem de IA-022).

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo import cofre
from mapasfacil_nucleo.agente import tools
from mapasfacil_nucleo.agente.tools import executar
from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.camadas.resolver import ResultadoResolucao
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_shapefile_geografico

FIXTURES = Path(__file__).parent / "fixtures" / "wfs"
CHAVE_TESTE = "sk-authkey-agente-nao-pode-vazar"


@pytest.fixture(autouse=True)
def _cofre_memoria():
    mem = cofre.BackendMemoria()
    cofre.configurar_backend(mem)
    cofre.definir("sema_authkey", CHAVE_TESTE)
    yield mem
    cofre.configurar_backend(None)


@pytest.fixture(autouse=True)
def _sem_transporte_real():
    yield
    http.configurar_transporte(None)


@pytest.fixture
def pasta_com_atp(tmp_path: Path) -> Path:
    """ATP geográfico (EPSG:4674) sobreposto ao polígono da fixture WFS."""
    shp = tmp_path / "SHP"
    escrever_shapefile_geografico(shp / "ATP.shp", lon=-58.0, lat=-11.0, delta=0.005)
    workspace_servico.abrir(str(tmp_path))
    yield tmp_path
    workspace_servico.fechar()


def _transporte_fixture(nome: str, *, content_type: str = "application/json"):
    corpo = (FIXTURES / nome).read_bytes()
    return lambda url, timeout: http.RespostaHttp(status=200, corpo=corpo, content_type=content_type)


# --------------------------------------------------------------------------- consultar_sema


def test_consultar_sema_parametro_obrigatorio_ausente() -> None:
    r = executar("consultar_sema", {}, {})
    assert r["ok"] is False
    assert r["codigo"] == "NU-001"


def test_consultar_sema_sem_workspace() -> None:
    workspace_servico.fechar()
    r = executar("consultar_sema", {"camada": "embargos_siga"}, {})
    assert r["codigo"] == "NU-040"


def test_consultar_sema_sem_atp_no_workspace(tmp_path: Path) -> None:
    (tmp_path / "SHP").mkdir()
    workspace_servico.abrir(str(tmp_path))
    try:
        r = executar("consultar_sema", {"camada": "embargos_siga"}, {})
        assert r["codigo"] == "NU-041"
    finally:
        workspace_servico.fechar()


def test_consultar_sema_devolve_contagem_e_area_sem_geometria(pasta_com_atp: Path) -> None:
    http.configurar_transporte(_transporte_fixture("embargos_siga_getfeature.json"))
    r = executar("consultar_sema", {"camada": "embargos_siga"}, {})
    assert r["ok"] is True
    assert r["contagem"] == 1
    assert r["area_ha"] > 0
    assert r["recortado_no_imovel"] is True
    texto = str(r)
    assert CHAVE_TESTE not in texto
    assert "geometrias" not in r
    assert "geometria" not in r


def test_consultar_sema_sem_recortar_no_imovel(pasta_com_atp: Path) -> None:
    http.configurar_transporte(_transporte_fixture("embargos_siga_getfeature.json"))
    r = executar("consultar_sema", {"camada": "embargos_siga", "recortar_no_imovel": False}, {})
    assert r["ok"] is True
    assert r["recortado_no_imovel"] is False
    assert r["contagem"] == 1


def test_consultar_sema_camada_vazia_no_recorte(pasta_com_atp: Path) -> None:
    http.configurar_transporte(_transporte_fixture("vazio_getfeature.json"))
    r = executar("consultar_sema", {"camada": "embargos_siga"}, {})
    assert r["ok"] is True
    assert r["contagem"] == 0
    assert r["area_ha"] == 0.0
    assert any(a["codigo"] == "NU-120" for a in r["avisos"])


def test_consultar_sema_sem_chave_configurada_propaga_erro_tipado(pasta_com_atp: Path) -> None:
    cofre.apagar("sema_authkey")
    r = executar("consultar_sema", {"camada": "embargos_siga"}, {})
    assert r["ok"] is False
    assert r["codigo"] == "NU-102"


def test_consultar_sema_recusa_camada_fora_do_catalogo() -> None:
    r = executar("consultar_sema", {"camada": "camada_inventada"}, {})
    assert r["codigo"] == tools.CODIGO_CATALOGO


# --------------------------------------------------------------------------- distancia_ate


def test_distancia_ate_parametro_obrigatorio_invalido() -> None:
    r = executar("distancia_ate", {"alvo": "marte"}, {})
    assert r["ok"] is False
    assert r["codigo"] == "NU-001"


def test_distancia_ate_sem_workspace() -> None:
    workspace_servico.fechar()
    r = executar("distancia_ate", {"alvo": "ti"}, {})
    assert r["codigo"] == "NU-040"


def test_distancia_ate_encontra_no_primeiro_raio(
    pasta_com_atp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shapely.geometry import Point

    chamadas: list[float] = []

    def fake_resolver(fonte, bbox, crs, *, guard, **_kw):
        chamadas.append(bbox)
        return ResultadoResolucao(
            camada_id=fonte,
            layer="Funai:tis_poligonais",
            tema="areas_protegidas",
            arquivo_rel="SHP/_camadas/fake.shp",
            epsg=4674,
            feicoes=1,
            vazia=False,
            parcial=False,
            origem_cache="miss",
            avisos=[],
            geometrias=[Point(-58.1, -11.1).buffer(0.001)],
        )

    monkeypatch.setattr(tools, "resolver_camada", fake_resolver)
    r = executar("distancia_ate", {"alvo": "ti"}, {})
    assert r["ok"] is True
    assert r["camada"] == "terras_indigenas_funai"
    assert r["distancia_km"] is not None
    assert r["distancia_km"] >= 0
    assert len(chamadas) == 1  # achou já no primeiro raio de busca


def test_distancia_ate_amplia_raio_ate_encontrar(
    pasta_com_atp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shapely.geometry import Point

    chamadas: list[Any] = []

    def fake_resolver(fonte, bbox, crs, *, guard, **_kw):
        chamadas.append(bbox)
        vazia = len(chamadas) < 3  # só acha no 3º raio
        geometrias = [] if vazia else [Point(-58.2, -11.2).buffer(0.001)]
        return ResultadoResolucao(
            camada_id=fonte,
            layer="Geoportal:UNIDADES_CONSERVACAO",
            tema="areas_protegidas",
            arquivo_rel="SHP/_camadas/fake.shp",
            epsg=4674,
            feicoes=len(geometrias),
            vazia=vazia,
            parcial=False,
            origem_cache="miss",
            avisos=[],
            geometrias=geometrias,
        )

    monkeypatch.setattr(tools, "resolver_camada", fake_resolver)
    r = executar("distancia_ate", {"alvo": "uc"}, {})
    assert r["ok"] is True
    assert r["distancia_km"] is not None
    assert len(chamadas) == 3


def test_distancia_ate_nada_encontrado_em_nenhum_raio(
    pasta_com_atp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_resolver(fonte, bbox, crs, *, guard, **_kw):
        return ResultadoResolucao(
            camada_id=fonte,
            layer="Geoportal:AREA_EMBARGADA_SIGA_POLIGONO",
            tema="embargos",
            arquivo_rel="SHP/_camadas/fake.shp",
            epsg=4674,
            feicoes=0,
            vazia=True,
            parcial=False,
            origem_cache="miss",
            avisos=[{"codigo": "NU-120", "mensagem": "vazio"}],
            geometrias=[],
        )

    monkeypatch.setattr(tools, "resolver_camada", fake_resolver)
    r = executar("distancia_ate", {"alvo": "embargo"}, {})
    assert r["ok"] is True
    assert r["distancia_km"] is None


def test_distancia_ate_erro_do_resolver_propaga_tipado(
    pasta_com_atp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mapasfacil_nucleo.erros import ErroNucleo

    def fake_resolver(fonte, bbox, crs, *, guard, **_kw):
        raise ErroNucleo("NU-102", "chave ausente")

    monkeypatch.setattr(tools, "resolver_camada", fake_resolver)
    r = executar("distancia_ate", {"alvo": "ti"}, {})
    assert r["ok"] is False
    assert r["codigo"] == "NU-102"
