import shutil
import tempfile
from pathlib import Path
import pymupdf
import pytest

from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_pdf import registrar_tools_pdf
from mapasfacil_nucleo.protocolo import Emissor


@pytest.fixture
def ws_pdf():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_pdf_")
    ws_path = Path(temp_dir)
    mapas_dir = ws_path / "Mapas"
    mapas_dir.mkdir(parents=True)

    # Criar 2 PDFs sintéticos para testes
    doc1 = pymupdf.open()
    page1 = doc1.new_page(width=595, height=842)  # A4
    page1.insert_text((50, 72), "Documento 1 - Mapa da Fazenda", fontsize=16)
    caminho_doc1 = mapas_dir / "mapa1.pdf"
    doc1.save(str(caminho_doc1))
    doc1.close()

    doc2 = pymupdf.open()
    page2 = doc2.new_page(width=595, height=842)
    page2.insert_text((50, 72), "Documento 2 - Tabela de Cobertura", fontsize=16)
    caminho_doc2 = mapas_dir / "tabela2.pdf"
    doc2.save(str(caminho_doc2))
    doc2.close()

    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_pdf_preview(ws_pdf):
    registro = RegistroFerramentas()
    registrar_tools_pdf(registro)
    eventos = []
    emissor = Emissor("req-p1", sink=lambda evt: eventos.append(evt))

    ctx = {"workspace": ws_pdf, "emissor": emissor}
    res = registro.executar("pdf_preview", {"caminho_pdf": "Mapas/mapa1.pdf", "pagina": 1}, ctx)

    assert res["ok"] is True
    assert "preview_caminho" in res
    assert (ws_pdf / res["preview_caminho"]).exists()

    # Evento agente.preview emitido
    evts_prev = [e for e in eventos if e["evento"] == "agente.preview"]
    assert len(evts_prev) == 1
    assert evts_prev[0]["dados"]["caminho"] == res["preview_caminho"]
    assert evts_prev[0]["dados"]["pagina"] == 1


def test_pdf_texto(ws_pdf):
    registro = RegistroFerramentas()
    registrar_tools_pdf(registro)

    ctx = {"workspace": ws_pdf}
    res = registro.executar("pdf_texto", {"caminho_pdf": "Mapas/mapa1.pdf"}, ctx)

    assert res["ok"] is True
    assert res["total_paginas"] == 1
    assert "Mapa da Fazenda" in res["paginas"][0]["texto"]


def test_pdf_unir(ws_pdf):
    registro = RegistroFerramentas()
    registrar_tools_pdf(registro)
    eventos = []
    emissor = Emissor("req-p2", sink=lambda evt: eventos.append(evt))

    ctx = {"workspace": ws_pdf, "emissor": emissor}
    res = registro.executar(
        "pdf_unir",
        {"caminhos": ["Mapas/mapa1.pdf", "Mapas/tabela2.pdf"], "caminho_saida": "Mapas/completo.pdf"},
        ctx,
    )

    assert res["ok"] is True
    assert res["total_paginas"] == 2
    assert (ws_pdf / "Mapas" / "completo.pdf").exists()

    # Verificar que o PDF unificado tem as 2 páginas
    doc_unido = pymupdf.open(str(ws_pdf / "Mapas" / "completo.pdf"))
    assert len(doc_unido) == 2
    doc_unido.close()

    # Evento agente.arquivo emitido
    evts_arq = [e for e in eventos if e["evento"] == "agente.arquivo"]
    assert len(evts_arq) >= 1
    assert evts_arq[0]["dados"]["acao"] == "criacao"
    assert evts_arq[0]["dados"]["caminho"] == "Mapas/completo.pdf"
