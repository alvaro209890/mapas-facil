from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np

from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.quantitativos.calcular import calcular as calcular_quantitativos
from mapasfacil_nucleo.quantitativos.png_tabela import renderizar_png_tabela
from mapasfacil_nucleo.validacao.comparar_pdf import rasterizar_pdf
from tests.helpers_fixtures import montar_workspace_minimo


def _mapspec_com_tabela() -> dict:
    return {
        "titulo": "Dinâmica teste tabela",
        "template": "dinamica_retrato",
        "imovel": {
            "nome": "Fazenda Teste",
            "municipio": {"nome": "Vila Rica", "uf": "MT"},
            "geometria": "local.ATP",
        },
        "crs": "EPSG:31982",
        "escala": 60000,
        "camadas": [
            {"fonte": "local.ATP", "estilo": "perimetro_imovel", "ordem": 10},
            {"fonte": "local.AVN", "estilo": "avn", "ordem": 30},
        ],
        "elementos_layout": {"tabela": True, "minimapa": False},
        "metadados": [{"rotulo": "Fonte", "valor": "teste"}],
        "tabela": {"total_geral": True, "casas_decimais": 4},
        "saidas": ["pdf"],
        "saida": {"pasta": "Mapas", "nome_base": "com_tabela", "materializar_camadas_em": "SHP"},
    }


def test_pdf_nativo_sobrepoe_tabela(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    guard = WorkspaceGuard(tmp_path)
    fontes_idx = {"ATP": "dados/ATP.shp", "AVN": "dados/AVN.shp"}
    mapspec = _mapspec_com_tabela()

    quant = calcular_quantitativos(mapspec, guard=guard, fontes_idx=fontes_idx)
    png = tmp_path / "Mapas" / "recursos" / "tabela_quantitativos.png"
    renderizar_png_tabela(quant, png)

    pdf_path, artefatos = gerar_pdf_minimo(
        mapspec, guard=guard, fontes_idx=fontes_idx, png_tabela=png
    )
    assert artefatos["tabela_sobreposta"] is True
    soft = artefatos["validacao_dados"]["checks"]["soft"]
    assert any(c["id"] == "H14" and c["ok"] for c in soft)

    # Raster: faixa inferior deve ter pixels azuis do cabeçalho da tabela (#2E75B6).
    arr = rasterizar_pdf(pdf_path, dpi=72)
    faixa = arr[int(arr.shape[0] * 0.75) :, :, :]
    # Canal B alto e R/G médios — azul institucional
    azuis = np.sum(
        (faixa[:, :, 2] > 140) & (faixa[:, :, 0] < 100) & (faixa[:, :, 1] < 160)
    )
    assert azuis > 50, f"poucos pixels azuis na faixa da tabela: {azuis}"


def test_gerar_mapa_pdf_com_overlay(tmp_path: Path, repo_root: Path) -> None:
    import copy
    import json

    montar_workspace_minimo(tmp_path)
    guard = WorkspaceGuard(tmp_path)
    fontes_idx = {"ATP": "dados/ATP.shp", "AVN": "dados/AVN.shp", "AUAS": "dados/AUAS.shp"}
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    mapspec = copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8")))
    mapspec["camadas"] = [c for c in mapspec["camadas"] if c["fonte"].startswith("local.")]
    mapspec["saidas"] = ["pdf", "png"]
    mapspec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "com_overlay",
        "materializar_camadas_em": "SHP",
    }

    resultado = gerar_mapa(mapspec, guard, fontes_idx)
    assert resultado.get("tabela_sobreposta") is True
    assert (tmp_path / resultado["png_tabela"]).exists()
    pdf = tmp_path / resultado["pdf"]
    assert pdf.exists()
    doc = fitz.open(pdf)
    assert doc.page_count == 1
    doc.close()


def test_pdf_sem_tabela_nao_sobrepoe(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    guard = WorkspaceGuard(tmp_path)
    fontes_idx = {"ATP": "dados/ATP.shp"}
    mapspec = _mapspec_com_tabela()
    mapspec["elementos_layout"] = {"tabela": False}
    mapspec.pop("tabela", None)

    pdf_path, artefatos = gerar_pdf_minimo(mapspec, guard=guard, fontes_idx=fontes_idx)
    assert artefatos["tabela_sobreposta"] is False
    assert pdf_path.exists()
