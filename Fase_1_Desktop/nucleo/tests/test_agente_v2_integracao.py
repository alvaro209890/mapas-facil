import tempfile
import shutil
from pathlib import Path
import pytest

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, carregar_todas_ferramentas_v2
from mapasfacil_nucleo.agente import tools as tools_legado


@pytest.fixture
def ws_integ():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_integ_")
    ws_path = Path(temp_dir)
    (ws_path / "Mapas").mkdir(parents=True)
    (ws_path / "SHP").mkdir(parents=True)
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_carregar_todas_ferramentas_v2(ws_integ):
    reg = carregar_todas_ferramentas_v2()

    # Checar presença de categorias
    categorias = {t.categoria for t in reg.listar()}
    assert "workspace" in categorias
    assert "geo" in categorias
    assert "layout" in categorias
    assert "pdf" in categorias
    assert "visao" in categorias
    assert "mapa" in categorias
    assert "skills" in categorias
    assert "memoria" in categorias
    assert "execucao" in categorias

    # Checar tools específicas requeridas pelo prompt
    nomes = reg.nomes_tools()
    esperadas = [
        # workspace
        "workspace_listar", "workspace_ler", "workspace_escrever",
        "workspace_mover", "workspace_apagar", "workspace_estat",
        # geo
        "geo_inspecionar", "geo_area", "geo_recortar",
        "geo_dissolver", "geo_intersectar", "geo_reprojetar",
        # layout
        "layout_ler", "layout_editar", "layout_medir", "layout_validar", "layout_renderizar",
        # pdf
        "pdf_preview", "pdf_texto", "pdf_unir",
        # visao
        "visao_analisar",
        # mapa
        "mapa_validar", "mapa_gerar", "versao_listar", "versao_restaurar",
        # memoria / skills
        "skill_listar", "skill_ler", "memoria_ler", "memoria_gravar",
        # python_exec fail closed
        "python_exec",
        # preservadas úteis
        "perguntar", "consultar_catalogo",
    ]
    for exp in esperadas:
        assert exp in nomes, f"Tool esperada ausente: {exp}"


def test_compatibilidade_tools_legado_executa_novas_ferramentas(ws_integ):
    # tools.executar deve conseguir despachar para as novas ferramentas v2
    ctx = {"workspace": ws_integ}
    res = tools_legado.executar("workspace_listar", {}, ctx)
    assert res["ok"] is True
    assert "itens" in res
