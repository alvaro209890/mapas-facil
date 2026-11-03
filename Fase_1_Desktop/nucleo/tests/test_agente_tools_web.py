# W5-12/W5-15 — tools do chat web e persistência do MapSpec por versão.
#
# Critério do plano: `definir_folha`, `listar_versoes`, `restaurar_versao` e
# `explicar_validacao` respondem pelo caminho real (workspace + galeria), e
# "volta pra versão 1" cria versão nova sem apagar artefato nenhum.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo import mapspec_store
from mapasfacil_nucleo.agente.tools import executar, schemas_openai
from mapasfacil_nucleo.galeria.montar import montar_mapspec
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MAPASFACIL_MODO", "servidor")
    monkeypatch.chdir(tmp_path)
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    yield tmp_path
    workspace_servico.fechar()


@pytest.fixture
def ctx(pasta: Path) -> dict[str, Any]:
    mapspec = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta))["mapspec"]
    return {"mapspec": mapspec}


# ------------------------------------------------------------------ mapspec_store


def test_store_grava_e_le_a_versao(ctx: dict[str, Any]):
    mapspec = {**ctx["mapspec"], "versao": 1}
    caminho = mapspec_store.salvar(mapspec)
    assert caminho.name == "mapspec.json"
    assert caminho.parent.name == "v001"
    assert mapspec_store.carregar(1)["titulo"] == mapspec["titulo"]
    assert mapspec_store.carregar(9) is None
    assert mapspec_store.ultima() == 1


def test_store_lista_da_mais_nova_para_a_mais_antiga(ctx: dict[str, Any]):
    for numero in (1, 2, 3):
        mapspec_store.salvar({**ctx["mapspec"], "versao": numero})
    lista = mapspec_store.listar()
    assert [v["versao"] for v in lista] == [3, 2, 1]
    assert all(v["folha"] for v in lista)


def test_store_sem_pasta_devolve_vazio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPASFACIL_MODO", "servidor")
    monkeypatch.chdir(tmp_path)
    assert mapspec_store.listar() == []
    assert mapspec_store.ultima() is None


def test_store_desktop_usa_pasta_de_versoes(ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MAPASFACIL_MODO", raising=False)
    caminho = mapspec_store.salvar({**ctx["mapspec"], "versao": 2})
    assert caminho.parent.name == "v002"
    assert caminho.parent.parent.name == "_versoes"


# --------------------------------------------------------------------- tools


def test_definir_folha_muda_formato_e_incrementa_versao(ctx: dict[str, Any]):
    antes = ctx["mapspec"]["versao"]
    saida = executar("definir_folha", {"formato": "A3", "orientacao": "paisagem"}, ctx)
    assert saida["ok"] is True, saida
    folha = ctx["mapspec"]["folha"]
    assert folha["formato"] == "A3"
    assert folha["orientacao"] == "paisagem"
    assert ctx["mapspec"]["versao"] == antes + 1


def test_definir_folha_recusa_formato_invalido(ctx: dict[str, Any]):
    saida = executar("definir_folha", {"formato": "A7"}, ctx)
    assert saida["ok"] is False
    assert saida["codigo"] == "NU-001"
    assert ctx["mapspec"]["folha"]["formato"] != "A7"


def test_listar_versoes_sem_nada_gerado(ctx: dict[str, Any]):
    saida = executar("listar_versoes", {}, ctx)
    assert saida["ok"] is True
    assert saida["versoes"] == []
    assert saida["total"] == 0


def test_restaurar_versao_sem_mapa_gerado_recusa(ctx: dict[str, Any]):
    saida = executar("restaurar_versao", {"versao": 1}, ctx)
    assert saida["ok"] is False
    assert saida["codigo"] == "NU-001"


def test_restaurar_versao_cria_versao_nova_sem_apagar_artefato(ctx: dict[str, Any], pasta: Path):
    # v1 gerada: A3 paisagem, com um PDF de mentira ao lado
    v1 = {**ctx["mapspec"], "versao": 1, "folha": {"formato": "A3", "orientacao": "paisagem"}}
    caminho = mapspec_store.salvar(v1)
    pdf_v1 = caminho.parent / "mapa.pdf"
    pdf_v1.write_bytes(b"%PDF-1.4 v1")

    # a conversa atual já está em v2 (A4 retrato)
    ctx["mapspec"] = {
        **ctx["mapspec"],
        "versao": 2,
        "folha": {"formato": "A4", "orientacao": "retrato"},
    }
    saida = executar("restaurar_versao", {"versao": 1}, ctx)
    assert saida["ok"] is True, saida
    assert ctx["mapspec"]["folha"]["formato"] == "A3"
    assert ctx["mapspec"]["versao"] == 3
    assert saida["restaurada_de"] == 1
    assert ctx["mapspec"]["parent_id"] == v1["id"]
    # o artefato da v1 continua exatamente onde estava
    assert pdf_v1.read_bytes() == b"%PDF-1.4 v1"


def test_explicar_validacao_sem_relatorio(ctx: dict[str, Any]):
    mapspec_store.salvar({**ctx["mapspec"], "versao": 1})
    saida = executar("explicar_validacao", {}, ctx)
    assert saida["ok"] is False
    assert saida["codigo"] == "NU-001"


def _escrever_relatorio(ctx: dict[str, Any], checks: dict[str, Any]) -> None:
    pasta = mapspec_store.pasta_da_versao(1)
    pasta.mkdir(parents=True, exist_ok=True)
    (_pasta := pasta / "mapa_validacao.json").write_text(
        json.dumps({"motor": "nativo", "confianca": "estrutural", "checks": checks}),
        encoding="utf-8",
    )


def test_explicar_validacao_traduz_falha_hard(ctx: dict[str, Any]):
    mapspec_store.salvar({**ctx["mapspec"], "versao": 1})
    _escrever_relatorio(
        ctx,
        {
            "hard": [
                {"id": "H01", "ok": True, "mensagem": "MXD gerado (nativo)"},
                {"id": "H17", "ok": False, "mensagem": "AUAS 12,4 ha fora da ATP"},
            ],
            "soft": [{"id": "A01", "ok": False, "mensagem": "escala arredondada"}],
        },
    )
    saida = executar("explicar_validacao", {}, ctx)
    assert saida["ok"] is True, saida
    dados = saida
    assert dados["conforme"] is False
    assert dados["falhas"][0]["id"] == "H17"
    assert "recibo do CAR" in dados["falhas"][0]["o_que_e"]
    assert "NÃO" in dados["veredito"]
    assert dados["avisos"][0]["id"] == "A01"


def test_explicar_validacao_conforme_quando_tudo_ok(ctx: dict[str, Any]):
    mapspec_store.salvar({**ctx["mapspec"], "versao": 1})
    _escrever_relatorio(ctx, {"hard": [{"id": "H01", "ok": True, "mensagem": "ok"}], "soft": []})
    dados = executar("explicar_validacao", {}, ctx)
    assert dados["conforme"] is True
    assert dados["falhas"] == []


def test_as_quatro_tools_entram_no_schema_do_provedor():
    nomes = {s["function"]["name"] for s in schemas_openai()}
    assert {"definir_folha", "listar_versoes", "restaurar_versao", "explicar_validacao"} <= nomes
