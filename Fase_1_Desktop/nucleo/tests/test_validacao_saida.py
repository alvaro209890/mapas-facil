from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from mapasfacil_nucleo.validacao.saida import (
    LISTA_NEGRA_S11,
    executar_checks_saida,
    verificar_h01_fontes_quebradas,
    verificar_pdf,
    verificar_s11_texto_herdado,
)
from tests.helpers_fixtures import escrever_pdf_cor_solido


def _pdf_com_texto(tmp_path: Path, texto: str) -> Path:
    caminho = tmp_path / "com_texto.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 retrato em pt
    page.insert_text((72, 72), texto, fontsize=12)
    doc.save(caminho)
    doc.close()
    return caminho


def test_h01_sem_quebradas() -> None:
    ok = verificar_h01_fontes_quebradas({"quebradas": []})
    assert ok["ok"] is True
    falha = verificar_h01_fontes_quebradas({"quebradas": ["AC"]})
    assert falha["ok"] is False


def test_h02_h03_h09_pdf(tmp_path: Path) -> None:
    pdf = _pdf_com_texto(
        tmp_path,
        "Dinâmica 2026\nEscala: 1:60000\nSatélite/Sensor PLANET\nFonte WMS-SEMA",
    )
    mapspec = {
        "titulo": "Dinâmica 2026",
        "escala": 60000,
        "metadados": [
            {"rotulo": "Satélite/Sensor", "valor": "PLANET"},
            {"rotulo": "Fonte", "valor": "WMS-SEMA"},
        ],
    }
    template = {"formato_pagina": {"mm": [210, 297], "orientacao": "retrato"}}
    hard, soft = verificar_pdf(pdf, mapspec, template=template)
    ids = {c["id"] for c in hard}
    assert "H02" in ids and "H03" in ids and "H09" in ids
    assert all(c["ok"] for c in hard if c["id"] in ("H02", "H03"))


def test_s11_lista_negra() -> None:
    mapspec = {"imovel": {"nome": "Fazenda A", "municipio": {"nome": "Vila Rica"}}}
    ok = verificar_s11_texto_herdado("Mapa limpo", mapspec)
    assert ok["ok"] is True
    for termo in LISTA_NEGRA_S11[:2]:
        falha = verificar_s11_texto_herdado(f"texto com {termo}", mapspec)
        assert falha["ok"] is False


def test_executar_checks_saida_arcpy(tmp_path: Path) -> None:
    pdf = tmp_path / "mapa.pdf"
    escrever_pdf_cor_solido(pdf, rgb=(40, 80, 120))
    mapspec = {"titulo": "X", "escala": 60000}
    rel = executar_checks_saida(
        mapspec,
        pdf_path=pdf,
        relatorio_arcpy={"quebradas": []},
        motor="arcpy",
    )
    assert rel["confianca"] == "arcpy"
    assert any(c["id"] == "H01" for c in rel["checks"]["hard"])


def test_executar_checks_saida_nativo(tmp_path: Path) -> None:
    pdf = tmp_path / "colorido.pdf"
    escrever_pdf_cor_solido(pdf, rgb=(40, 80, 120))
    mapspec = {"titulo": "Teste"}
    rel = executar_checks_saida(mapspec, pdf_path=pdf, motor="nativo")
    h09 = next(c for c in rel["checks"]["hard"] if c["id"] == "H09")
    assert h09["ok"] is True


def test_checks_h18_h19_h20_mxd(tmp_path: Path) -> None:
    """W10-12: valida checks H18 (sem segredo), H19 (estrutural) e H20 (dados relativos)."""
    from mapasfacil_nucleo.config import raiz_repositorio
    mxd_base = raiz_repositorio() / "shared" / "templates" / "Dinamica_retrato.mxd"
    if not mxd_base.exists():
        pytest.skip("Template base não encontrado")

    pdf = tmp_path / "mapa.pdf"
    escrever_pdf_cor_solido(pdf, rgb=(40, 80, 120))

    mapspec = {"titulo": "Mapa Dinâmica"}
    rel = executar_checks_saida(
        mapspec,
        pdf_path=pdf,
        mxd_path=mxd_base,
        pasta_pacote=tmp_path,
        motor="binario",
    )

    ids = {c["id"] for c in rel["checks"]["hard"]}
    assert "H18" in ids
    assert "H19" in ids
    assert "H20" in ids

    h18 = next(c for c in rel["checks"]["hard"] if c["id"] == "H18")
    h19 = next(c for c in rel["checks"]["hard"] if c["id"] == "H19")
    h20 = next(c for c in rel["checks"]["hard"] if c["id"] == "H20")

    assert h18["ok"] is True
    assert h19["ok"] is True
    assert h20["ok"] is True
