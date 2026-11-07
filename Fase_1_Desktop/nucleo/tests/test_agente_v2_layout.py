import shutil
import tempfile
from pathlib import Path
import pytest

from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_layout import registrar_tools_layout
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.protocolo import Emissor


@pytest.fixture
def ws_layout():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_layout_")
    ws_path = Path(temp_dir)
    (ws_path / "Mapas").mkdir(parents=True)
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def ctx_layout(ws_layout):
    mapspec_exemplo = {
        "id": "ms-001",
        "versao": 1,
        "template": "serie_dinamica_2026",
        "folha": {
            "tamanho": "A4",
            "orientacao": "retrato",
            "largura_mm": 210.0,
            "altura_mm": 297.0,
            "margem_mm": 10.0,
        },
        "saida": {
            "pasta": "Mapas",
            "nome_base": "mapa_teste",
        },
    }
    return {"workspace": ws_layout, "mapspec": mapspec_exemplo}


def test_layout_ler(ctx_layout):
    registro = RegistroFerramentas()
    registrar_tools_layout(registro)

    res = registro.executar("layout_ler", {}, ctx_layout)
    assert res["ok"] is True
    assert "layout_spec" in res
    assert "mapa" in res["elementos"]
    assert "titulo" in res["elementos"]
    assert res["dimensoes_mm"]["largura"] == pytest.approx(210.0, abs=0.5)
    assert res["dimensoes_mm"]["altura"] == pytest.approx(297.0, abs=0.5)


def test_layout_editar(ctx_layout):
    registro = RegistroFerramentas()
    registrar_tools_layout(registro)

    # Editar coordenadas do título no LayoutSpec
    res_edit = registro.executar(
        "layout_editar",
        {
            "elemento_id": "titulo",
            "propriedades": {"x0": 65.0, "y0": 10.0, "x1": 130.0, "y1": 25.0},
        },
        ctx_layout,
    )
    assert res_edit["ok"] is True
    assert res_edit["elemento_id"] == "titulo"
    assert res_edit["propriedades"]["x0"] == 65.0
    assert res_edit["propriedades"]["x1"] == 130.0

    # Ler novamente para confirmar persistência no MapSpec
    res_ler = registro.executar("layout_ler", {}, ctx_layout)
    assert res_ler["elementos"]["titulo"]["x0"] == 65.0
    assert res_ler["elementos"]["titulo"]["x1"] == 130.0


def test_layout_medir_com_pdf_real(ctx_layout, ws_layout):
    registro = RegistroFerramentas()
    registrar_tools_layout(registro)

    # Gerar um PDF real no workspace para teste de medição física
    guard = WorkspaceGuard(ws_layout)
    pdf_path, _ = gerar_pdf_minimo(ctx_layout["mapspec"], guard=guard, fontes_idx={})
    assert pdf_path.exists()

    rel_pdf = pdf_path.relative_to(ws_layout).as_posix()
    res_medir = registro.executar(
        "layout_medir",
        {"caminho_pdf": rel_pdf, "id": "medido_teste", "nome": "Layout Teste Medido"},
        ctx_layout,
    )

    assert res_medir["ok"] is True
    assert res_medir["id"] == "medido_teste"
    assert res_medir["orientacao"] == "retrato"
    assert "mapa" in res_medir["elementos"]
    assert "titulo" in res_medir["elementos"]
    assert res_medir["dimensoes_mm"]["largura"] > 0
    assert res_medir["dimensoes_mm"]["altura"] > 0


def test_layout_validar(ctx_layout):
    registro = RegistroFerramentas()
    registrar_tools_layout(registro)

    # Layout inicial válido
    res_val = registro.executar("layout_validar", {}, ctx_layout)
    assert res_val["ok"] is True
    assert res_val["valido"] is True

    # Introduzir elemento fora dos limites da folha (largura 210mm)
    registro.executar(
        "layout_editar",
        {"elemento_id": "titulo", "propriedades": {"x1": 250.0}},
        ctx_layout,
    )
    res_invalido = registro.executar("layout_validar", {}, ctx_layout)
    assert res_invalido["ok"] is True
    assert res_invalido["valido"] is False
    assert len(res_invalido["erros"]) > 0


def test_layout_renderizar_real(ctx_layout, ws_layout):
    registro = RegistroFerramentas()
    registrar_tools_layout(registro)
    eventos = []
    emissor = Emissor("req-lay-1", sink=lambda evt: eventos.append(evt))
    ctx_layout["emissor"] = emissor

    res_rend = registro.executar("layout_renderizar", {"formato": "pdf"}, ctx_layout)
    assert res_rend["ok"] is True
    assert res_rend["status"] == "renderizado"

    # Verificar que o PDF real existe no disco e não é vazio
    caminho_pdf = ws_layout / res_rend["caminho_pdf"]
    assert caminho_pdf.exists()
    assert caminho_pdf.stat().st_size > 1000

    # Verificar que o preview PNG real existe no disco
    caminho_prev = ws_layout / res_rend["preview"]
    assert caminho_prev.exists()
    assert caminho_prev.stat().st_size > 500

    # Verificar que o evento agente.preview foi emitido com o caminho real do arquivo
    evts = [e for e in eventos if e["evento"] == "agente.preview"]
    assert len(evts) == 1
    assert evts[0]["dados"]["caminho"] == res_rend["preview"]
