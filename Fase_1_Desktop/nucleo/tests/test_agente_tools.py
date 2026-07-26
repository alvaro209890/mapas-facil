# G5 — tools reais do agente (sem rede, sem chave). F1-06 §Catálogo de tools.

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.tools import (
    TOOLS_COM_DEPENDENCIA_PENDENTE,
    executar,
    nomes_tools,
    schemas_openai,
)
from mapasfacil_nucleo.galeria.montar import montar_mapspec
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    return tmp_path


@pytest.fixture
def ctx(pasta: Path) -> dict[str, Any]:
    """Contexto de turno já com o MapSpec da galeria adotado."""
    mapspec = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta))["mapspec"]
    return {"mapspec": mapspec}


# --------------------------------------------------------------------------- catálogo


def test_todas_as_tools_tem_schema_tipado():
    schemas = {s["function"]["name"]: s["function"] for s in schemas_openai()}
    assert set(schemas) == set(nomes_tools())
    for nome, fn in schemas.items():
        params = fn["parameters"]
        assert params["additionalProperties"] is False, f"{nome} aceita parâmetro livre"
        assert isinstance(params["properties"], dict)
        assert fn["description"] and not fn["description"].startswith("Tool "), nome


def test_nenhuma_tool_depende_de_peca_futura(ctx: dict[str, Any]):
    """Nenhuma tool é stub — a última (`analisar_referencia`) fechou em F1-07.

    A13 tirou `consultar_sema`/`distancia_ate` (camada.resolver real); F1-07 tirou
    `analisar_referencia` (agente/visao/).
    """
    pendentes = set()
    for nome in nomes_tools():
        resultado = executar(nome, {}, dict(ctx))
        if resultado.get("codigo") == "IA-022":
            pendentes.add(nome)
    assert pendentes == set(TOOLS_COM_DEPENDENCIA_PENDENTE)


def test_consultar_sema_recusa_camada_fora_do_catalogo():
    r = executar("consultar_sema", {"camada": "camada_inventada"}, {})
    assert r["codigo"] == limites.CODIGO_TOOL_INEXISTENTE


def test_listar_catalogo_pagina_em_30(pasta: Path):
    r = executar("listar_catalogo", {}, {})
    assert r["ok"] is True
    assert len(r["camadas"]) <= 30
    assert r["total_camadas"] >= len(r["camadas"])
    assert "perimetro_imovel" in r["estilos"]
    assert "dinamica_retrato" in r["templates"]


def test_listar_zip_nao_extrai(pasta: Path):
    alvo = pasta / "SIMCAR.zip"
    with zipfile.ZipFile(alvo, "w") as zf:
        zf.writestr("ATP.shp", b"conteudo")
        zf.writestr("ATP.dbf", b"conteudo")
    r = executar("listar_zip", {"arquivo": "SIMCAR.zip"}, {})
    assert r["ok"] is True
    assert r["total"] == 2
    assert r["shapefiles"] == ["ATP.shp"]
    assert not (pasta / "_extraido").exists()


# --------------------------------------------------------------------------- edição


def test_editar_camada_cria_nova_versao(ctx: dict[str, Any]):
    antes = ctx["mapspec"]
    r = executar("editar_camada", {"id": "avn", "legenda": "Vegetação nativa"}, ctx)
    assert r["ok"] is True, r
    assert r["versao"] == antes["versao"] + 1
    assert r["parent_id"] == antes["id"]
    assert any("legenda" in linha for linha in r["alteracoes"])
    # a versão anterior não foi mutada no lugar
    assert antes["versao"] == 1
    assert ctx["mapspec"]["versao"] == 2


def test_estilo_fora_do_catalogo_ia020_com_sugestao(ctx: dict[str, Any]):
    r = executar("editar_camada", {"id": "avn", "estilo": "avn_roxo_listrado"}, ctx)
    assert r["ok"] is False
    assert r["codigo"] == limites.CODIGO_TOOL_INEXISTENTE
    assert r["sugestao"] == "avn"
    assert ctx["mapspec"]["versao"] == 1  # nada mudou


def test_escala_fora_da_lista_recusada(ctx: dict[str, Any]):
    r = executar("definir_escala", {"escala": 12345}, ctx)
    assert r["ok"] is False
    assert r["escalas"]
    ok = executar("definir_escala", {"escala": "auto"}, ctx)
    assert ok["ok"] is True


def test_alternar_elemento_inverte_e_valida_nome(ctx: dict[str, Any]):
    ligado_antes = bool(ctx["mapspec"]["elementos_layout"].get("tabela"))
    r = executar("alternar_elemento", {"elemento": "tabela"}, ctx)
    assert r["ok"] is True
    assert ctx["mapspec"]["elementos_layout"]["tabela"] is (not ligado_antes)
    ruim = executar("alternar_elemento", {"elemento": "bussola_magica"}, ctx)
    assert ruim["codigo"] == limites.CODIGO_TOOL_INEXISTENTE


def test_filtro_com_sql_livre_recusado(ctx: dict[str, Any]):
    r = executar(
        "adicionar_camada",
        {
            "fonte": "catalogo.car_atp",
            "estilo": "perimetro_imovel",
            "nome_no_mxd": "CAR vizinho",
            "filtro": {"campo": "NOME", "operador": "DROP TABLE", "valor": "x"},
        },
        ctx,
    )
    assert r["ok"] is False
    assert r["operadores"]


def test_adicionar_e_remover_camada(ctx: dict[str, Any]):
    add = executar(
        "adicionar_camada",
        {
            "fonte": "catalogo.car_atp",
            "estilo": "perimetro_imovel",
            "nome_no_mxd": "CAR vizinho",
            "ordem": 95,
        },
        ctx,
    )
    assert add["ok"] is True, add
    ids = [c["id"] for c in ctx["mapspec"]["camadas"]]
    assert "car_atp" in ids
    rem = executar("remover_camada", {"id": "car_atp"}, ctx)
    assert rem["ok"] is True
    assert "car_atp" not in [c["id"] for c in ctx["mapspec"]["camadas"]]


def test_nao_remove_ultima_camada(ctx: dict[str, Any]):
    while len(ctx["mapspec"]["camadas"]) > 1:
        alvo = ctx["mapspec"]["camadas"][-1]["id"]
        assert executar("remover_camada", {"id": alvo}, ctx)["ok"] is True
    r = executar("remover_camada", {"id": ctx["mapspec"]["camadas"][0]["id"]}, ctx)
    assert r["ok"] is False


def test_metadados_definir_e_remover(ctx: dict[str, Any]):
    executar("editar_metadados", {"rotulo": "Fonte", "valor": "WMS-SEMA 2026"}, ctx)
    linhas = {m["rotulo"]: m["valor"] for m in ctx["mapspec"]["metadados"]}
    assert linhas["Fonte"] == "WMS-SEMA 2026"
    executar("editar_metadados", {"acao": "remover", "rotulo": "Fonte"}, ctx)
    assert "Fonte" not in {m["rotulo"] for m in ctx["mapspec"]["metadados"]}


def test_criar_mapa_do_zero_valida(pasta: Path):
    ctx: dict[str, Any] = {}
    r = executar("criar_mapa", {"template": "dinamica_retrato"}, ctx)
    assert r["ok"] is True, r
    assert executar("validar_mapspec", {}, ctx)["valido"] is True
    ruim = executar("criar_mapa", {"template": "dinamica_retratoo"}, {})
    assert ruim["sugestao"] == "dinamica_retrato"


# --------------------------------------------------------------------------- fluxo


def test_calcular_quantitativos_devolve_matriz(ctx: dict[str, Any]):
    r = executar("calcular_quantitativos", {}, ctx)
    assert r["ok"] is True, r
    assert r["areas_ha"]["area_total_ha"] > 0
    assert "linhas" in r and r["colunas"]
    texto = json.dumps(r, ensure_ascii=False)
    assert "POLYGON" not in texto.upper()


def test_gerar_mapa_produz_artefatos(ctx: dict[str, Any], pasta: Path):
    r = executar("gerar_mapa", {"saidas": ["pdf", "xlsx"]}, ctx)
    assert r["ok"] is True, r
    assert r["artefatos"]["pdf"].endswith(".pdf")
    assert (pasta / r["artefatos"]["pdf"]).is_file()
    assert (pasta / r["artefatos"]["xlsx"]).is_file()
    assert not Path(r["artefatos"]["pdf"]).is_absolute()
    assert ctx["mapas_gerados"]


def test_gerar_planilha(ctx: dict[str, Any], pasta: Path):
    r = executar("gerar_planilha", {}, ctx)
    assert r["ok"] is True, r
    assert (pasta / r["xlsx"]).is_file()
    assert "conferencia" in r


def test_gerar_mapa_sem_mapspec_erra_tipado(pasta: Path):
    r = executar("gerar_mapa", {}, {})
    assert r["ok"] is False
    assert r["codigo"] == "NU-201"


def test_resultado_de_tool_respeita_teto(ctx: dict[str, Any]):
    for nome in ("estado_do_projeto", "listar_arquivos", "listar_catalogo"):
        resultado = executar(nome, {}, dict(ctx))
        texto = json.dumps(resultado, ensure_ascii=False, default=str)
        assert limites.estimar_tokens(texto) <= limites.RESULTADO_TOOL_MAX
