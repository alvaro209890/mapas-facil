from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.quantitativos.calcular import calcular as calcular_quantitativos
from mapasfacil_nucleo.validacao.comparar_pdf import (
    comparar_pdf,
    medir_diferenca_raster,
    rasterizar_pdf,
)
from tests.helpers_fixtures import escrever_pdf_cor_solido, montar_workspace_minimo


def test_rasterizar_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    escrever_pdf_cor_solido(pdf, rgb=(255, 0, 0))
    arr = rasterizar_pdf(pdf, dpi=72)
    assert arr.shape[2] == 3
    assert arr.mean() > 0


def test_pdfs_identicos_diferenca_zero(tmp_path: Path) -> None:
    pdf = tmp_path / "ref.pdf"
    escrever_pdf_cor_solido(pdf, rgb=(10, 20, 30))
    copia = tmp_path / "gerado.pdf"
    copia.write_bytes(pdf.read_bytes())

    resultado = comparar_pdf(copia, pdf, dpi=72, tolerancia_pct=0.3)
    assert resultado["ok"] is True
    assert resultado["diferenca_pct"] == 0.0


def test_pdfs_diferentes_excedem_tolerancia(tmp_path: Path) -> None:
    ref = tmp_path / "ref.pdf"
    ger = tmp_path / "ger.pdf"
    escrever_pdf_cor_solido(ref, rgb=(0, 0, 0))
    escrever_pdf_cor_solido(ger, rgb=(255, 255, 255))

    resultado = comparar_pdf(ger, ref, dpi=72, tolerancia_pct=0.3)
    assert resultado["ok"] is False
    assert resultado["diferenca_pct"] > 0.3


def test_medir_diferenca_recorta_tamanhos() -> None:
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    b = np.zeros((8, 12, 3), dtype=np.uint8)
    medidas = medir_diferenca_raster(a, b)
    assert medidas["dimensoes"]["comparadas"] == [8, 10]


def test_calcular_quantitativos_workspace(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    guard = WorkspaceGuard(tmp_path)
    fontes_idx = {
        "ATP": "dados/ATP.shp",
        "AVN": "dados/AVN.shp",
        "AUAS": "dados/AUAS.shp",
    }
    mapspec = {
        "imovel": {"nome": "Fazenda Teste"},
        "camadas": [
            {"fonte": "local.ATP", "estilo": "perimetro_imovel"},
            {"fonte": "local.AVN", "estilo": "avn"},
            {"fonte": "local.AUAS", "estilo": "auas"},
        ],
        "tabela": {"total_geral": True, "casas_decimais": 4},
    }
    resultado = calcular_quantitativos(mapspec, guard=guard, fontes_idx=fontes_idx)
    assert len(resultado["linhas"]) == 1
    assert resultado["linhas"][0][0] == "Fazenda Teste"
    assert resultado["areas"]["area_total_ha"] == 100.0
    assert resultado["areas"]["avn_ha"] == 64.0
    assert resultado["areas"]["auas_ha"] == 16.0
    assert resultado["total_geral"] == 80.0


def test_gerar_mapa_com_quantitativos(tmp_path: Path, repo_root: Path) -> None:
    import copy
    import json

    montar_workspace_minimo(tmp_path)
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    mapspec = copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8")))
    mapspec["camadas"] = [c for c in mapspec["camadas"] if c["fonte"].startswith("local.")]
    mapspec["saidas"] = ["pdf"]
    mapspec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "Dinamica_quant",
        "materializar_camadas_em": "SHP",
    }

    fontes_idx = {
        "ATP": "dados/ATP.shp",
        "AVN": "dados/AVN.shp",
        "AUAS": "dados/AUAS.shp",
    }
    guard = WorkspaceGuard(tmp_path)
    resultado = gerar_mapa(mapspec, guard, fontes_idx)
    assert "quantitativos" in resultado
    assert resultado["quantitativos"]["linhas"][0][0] == "Fazenda Harmonia"
