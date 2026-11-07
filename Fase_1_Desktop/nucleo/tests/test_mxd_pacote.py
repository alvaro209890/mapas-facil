"""Testes de montagem do pacote de entrega MXD/SHP/Mapas (W10-10 / D37).

Valida:
1. Montagem completa de arquivo .zip com LEIA-ME.txt, MXD, SHP e Mapas;
2. Política D37: entrega preservada mesmo quando o MXD não é conforme (com aviso no LEIA-ME.txt);
3. Validação dos caminhos relativos e estrutura de diretórios.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.mxd_binario import (
    DocumentoMxd,
    OpcoesPacote,
    montar_pacote_zip,
)

_RAIZ = raiz_repositorio()
_PASTA_TEMPLATES = _RAIZ / "shared" / "templates"


def test_montar_pacote_zip_padrao_pdf_first_sem_mxd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida montagem padrão PDF-first: omite MXD/ mesmo se documento fornecido, preserva Mapas/ e SHP/."""
    monkeypatch.delenv("MF_MXD", raising=False)
    pasta_versao = tmp_path / "versao_padrao"
    pasta_versao.mkdir()

    pasta_shp = pasta_versao / "SHP"
    pasta_shp.mkdir()
    (pasta_shp / "ATP.shp").write_bytes(b"ATP_SHAPEFILE")

    pasta_mapas = pasta_versao / "Mapas"
    pasta_mapas.mkdir()
    (pasta_mapas / "Dinamica_2026.pdf").write_bytes(b"%PDF-1.4 simulado")
    (pasta_mapas / "Quantitativos.xlsx").write_bytes(b"XLSX simulado")

    mxd_base = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    mxd_doc = DocumentoMxd.abrir(mxd_base) if mxd_base.exists() else None

    # Opcoes padrão: incluir_mxd=False
    opcoes = OpcoesPacote(
        nome_imovel="Fazenda Primavera",
        nome_template="Dinamica_2026",
        versao=1,
        mxd_doc=mxd_doc,
        mxd_conforme=True,
    )

    zip_saida = tmp_path / "pacote_pdf_first.zip"
    montar_pacote_zip(pasta_versao, zip_saida, opcoes)

    assert zip_saida.exists()

    with zipfile.ZipFile(zip_saida, "r") as zf:
        nomes = zf.namelist()
        assert "LEIA-ME.txt" in nomes
        assert not any(n.startswith("MXD/") for n in nomes)
        assert "SHP/ATP.shp" in nomes
        assert "Mapas/Dinamica_2026.pdf" in nomes
        assert "XLSX/Quantitativos.xlsx" in nomes

        leia_me = zf.read("LEIA-ME.txt").decode("utf-8")
        assert "Fazenda Primavera" in leia_me
        assert "PDF" in leia_me
        assert "ArcMap 10.x" not in leia_me


def test_montar_pacote_zip_completo_conforme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida montagem de pacote com MXD quando explicitamente pedido com incluir_mxd=True e MF_MXD=1."""
    monkeypatch.setenv("MF_MXD", "1")
    pasta_versao = tmp_path / "versao_001"
    pasta_versao.mkdir()

    # Cria dados simulados de SHP
    pasta_shp = pasta_versao / "SHP"
    pasta_shp.mkdir()
    (pasta_shp / "ATP.shp").write_bytes(b"ATP_SHAPEFILE")
    (pasta_shp / "ATP.dbf").write_bytes(b"ATP_DBF")

    # Cria dados simulados de Mapas
    pasta_mapas = pasta_versao / "Mapas"
    pasta_mapas.mkdir()
    (pasta_mapas / "Dinamica_2026.pdf").write_bytes(b"%PDF-1.4 simulado")
    (pasta_mapas / "validacao.json").write_text('{"conforme": true}', encoding="utf-8")

    # Documento MXD simulado
    mxd_base = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    if not mxd_base.exists():
        pytest.skip("Template base não encontrado")
    mxd_doc = DocumentoMxd.abrir(mxd_base)

    opcoes = OpcoesPacote(
        nome_imovel="Fazenda Primavera",
        nome_template="Dinamica_2026",
        versao=1,
        mxd_doc=mxd_doc,
        mxd_conforme=True,
        incluir_mxd=True,
    )

    zip_saida = tmp_path / "pacote_entrega.zip"
    montar_pacote_zip(pasta_versao, zip_saida, opcoes)

    assert zip_saida.exists()

    with zipfile.ZipFile(zip_saida, "r") as zf:
        nomes = zf.namelist()
        assert "LEIA-ME.txt" in nomes
        assert "MXD/Dinamica_2026.mxd" in nomes
        assert "SHP/ATP.shp" in nomes
        assert "SHP/ATP.dbf" in nomes
        assert "Mapas/Dinamica_2026.pdf" in nomes
        assert "Mapas/validacao.json" in nomes

        # Lê LEIA-ME e valida conteúdo
        leia_me = zf.read("LEIA-ME.txt").decode("utf-8")
        assert "Fazenda Primavera" in leia_me
        assert "Repair Data Source" in leia_me
        assert "MXD/Dinamica_2026.mxd" in leia_me


def test_montar_pacote_zip_mxd_nao_conforme_politica_d37(tmp_path: Path) -> None:
    """Valida que quando o MXD não é conforme, Mapas e SHP são entregues com aviso MX-020."""
    pasta_versao = tmp_path / "versao_002"
    pasta_versao.mkdir()

    pasta_shp = pasta_versao / "SHP"
    pasta_shp.mkdir()
    (pasta_shp / "PERIMETRO.shp").write_bytes(b"PERIMETRO")

    pasta_mapas = pasta_versao / "Mapas"
    pasta_mapas.mkdir()
    (pasta_mapas / "Mapa_A0.pdf").write_bytes(b"%PDF A0")

    opcoes = OpcoesPacote(
        nome_imovel="Fazenda São José",
        nome_template="Mapa_A0",
        versao=2,
        mxd_doc=None,
        mxd_conforme=False,
        codigo_aviso_mxd="MX-020",
    )

    zip_saida = tmp_path / "pacote_sem_mxd.zip"
    montar_pacote_zip(pasta_versao, zip_saida, opcoes)

    assert zip_saida.exists()

    with zipfile.ZipFile(zip_saida, "r") as zf:
        nomes = zf.namelist()
        assert "LEIA-ME.txt" in nomes
        assert "MXD/Mapa_A0.mxd" not in nomes  # Omitido conforme D37
        assert "SHP/PERIMETRO.shp" in nomes
        assert "Mapas/Mapa_A0.pdf" in nomes

        leia_me = zf.read("LEIA-ME.txt").decode("utf-8")
        assert "AVISO [MX-020]: O arquivo .mxd não foi incluído" in leia_me
