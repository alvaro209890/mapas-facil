import shutil
import tempfile
from pathlib import Path
import pytest

from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_memoria import registrar_tools_memoria
from mapasfacil_nucleo.agente.tools_mapa import registrar_tools_mapa
from mapasfacil_nucleo.agente.tools_visao import registrar_tools_visao


@pytest.fixture
def ws_memoria():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_mem_")
    ws_path = Path(temp_dir)
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_skills_listar_e_ler():
    registro = RegistroFerramentas()
    registrar_tools_memoria(registro)

    res_lista = registro.executar("skill_listar", {}, {})
    assert res_lista["ok"] is True
    skills = res_lista["skills"]
    assert len(skills) >= 5
    nomes = [s["nome"] for s in skills]
    assert "cartografia-padrao" in nomes
    assert "analise-ambiental" in nomes

    res_ler = registro.executar("skill_ler", {"nome": "cartografia-padrao"}, {})
    assert res_ler["ok"] is True
    assert "Enquadramento e Margens" in res_ler["conteudo"]
    assert "15%" in res_ler["conteudo"]


def test_memoria_ler_e_gravar(ws_memoria):
    registro = RegistroFerramentas()
    registrar_tools_memoria(registro)

    ctx = {"workspace": ws_memoria}
    # Memória vazia inicialmente
    res_ler1 = registro.executar("memoria_ler", {}, ctx)
    assert res_ler1["ok"] is True
    assert res_ler1["conteudo"] == ""

    # Gravar memória
    res_grv = registro.executar("memoria_gravar", {"conteudo": "Imóvel com 2 glebas na zona oeste."}, ctx)
    assert res_grv["ok"] is True

    # Ler novamente
    res_ler2 = registro.executar("memoria_ler", {}, ctx)
    assert res_ler2["ok"] is True
    assert "2 glebas" in res_ler2["conteudo"]

    # Adicionar à memória
    registro.executar("memoria_gravar", {"adicionar": "CAR analisado e sem pendências."}, ctx)
    res_ler3 = registro.executar("memoria_ler", {}, ctx)
    assert "2 glebas" in res_ler3["conteudo"]
    assert "sem pendências" in res_ler3["conteudo"]


def test_mapa_aliases_e_versoes(ws_memoria):
    registro = RegistroFerramentas()
    registrar_tools_mapa(registro)

    mapas_dir = ws_memoria / "Mapas"
    mapas_dir.mkdir(parents=True)
    (mapas_dir / "mapa_v1.pdf").write_text("v1", encoding="utf-8")
    (mapas_dir / "mapa_v2.pdf").write_text("v2", encoding="utf-8")

    ctx = {"workspace": ws_memoria}
    res_versoes = registro.executar("versao_listar", {}, ctx)
    assert res_versoes["ok"] is True
    assert len(res_versoes["versoes"]) >= 2
