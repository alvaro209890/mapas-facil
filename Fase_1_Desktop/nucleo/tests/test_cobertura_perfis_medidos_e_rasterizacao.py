"""Prova formal de cobertura: 7 modelos da galeria e 26 templates cobertos por perfis medidos.

Gera PDFs sintéticos em retrato (Dinâmica 2026) e paisagem (Tipologia),
rasteriza para PNG e valida a integridade visual e estrutural.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import fitz  # PyMuPDF

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.galeria.catalogo import carregar_galeria
from mapasfacil_nucleo.layout import (
    LayoutSpec,
    carregar,
    obter_layout,
    perfil_do_layout,
    validar,
)
from mapasfacil_nucleo.motores.manifesto import carregar as carregar_manifesto
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.motores.perfil_pagina import caixas_fora_da_pagina
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm

_RAIZ = raiz_repositorio()


def test_cobertura_dos_7_modelos_da_galeria() -> None:
    """Provar que todos os 7 modelos da galeria possuem perfil medido válido."""
    galeria = carregar_galeria()
    modelos = galeria.get("modelos", [])
    assert len(modelos) == 7, f"Esperava 7 modelos na galeria, encontrou {len(modelos)}"

    for mod in modelos:
        mid = mod["id"]
        template_id = mod.get("template")
        assert template_id, f"Modelo {mid} sem template definido"

        spec = obter_layout(template_id)
        assert isinstance(spec, LayoutSpec), f"Falha ao resolver LayoutSpec para modelo {mid}"

        # Validação contra o schema oficial
        res_val = validar(spec)
        assert res_val["valido"] is True, f"Modelo {mid} gerou LayoutSpec inválido: {res_val['erros']}"

        # Conversão em PerfilPagina
        perfil = perfil_do_layout(spec)
        assert perfil.largura_mm > 0
        assert perfil.altura_mm > 0

        # Nenhuma caixa pode vazar da página
        fora = caixas_fora_da_pagina(perfil)
        assert not fora, f"Modelo {mid} possui caixas que vazam a página: {fora}"


def test_cobertura_dos_26_templates_do_manifesto() -> None:
    """Provar que todos os 26 templates do manifesto possuem perfil medido válido."""
    manifesto = carregar_manifesto()
    templates = manifesto.get("templates", [])
    assert len(templates) == 26, f"Esperava 26 templates no manifesto, encontrou {len(templates)}"

    for tpl in templates:
        tid = tpl["id"]
        spec = obter_layout(tid)
        assert isinstance(spec, LayoutSpec), f"Falha ao resolver LayoutSpec para template {tid}"

        res_val = validar(spec)
        assert res_val["valido"] is True, f"Template {tid} gerou LayoutSpec inválido: {res_val['erros']}"

        perfil = perfil_do_layout(spec)
        fora = caixas_fora_da_pagina(perfil)
        assert not fora, f"Template {tid} possui caixas que vazam a página: {fora}"


def test_gerar_pdf_sintetico_retrato_e_rasterizar(tmp_path: Path) -> None:
    """Gera PDF sintético retrato (Dinâmica 2026), rasteriza e confere conformidade."""
    pasta_shp = tmp_path / "SHP"
    pasta_shp.mkdir()
    escrever_shapefile_quadrado_utm(pasta_shp / "ATP.shp", nome="Harmonia_Sintetica", lado_m=4000)
    escrever_shapefile_quadrado_utm(pasta_shp / "AVN.shp", nome="AVN", lado_m=1200)

    guard = WorkspaceGuard(tmp_path)
    mapspec = {
        "titulo": "Dinâmica 2026 — Retrato Sintético",
        "template": "dinamica_retrato",
        "folha": {"formato": "A4", "orientacao": "retrato"},
        "imovel": {"nome": "Fazenda Harmonia Sintética", "geometria": "local.ATP"},
        "camadas": [
            {
                "id": "ATP",
                "nome_no_mxd": "Fazenda Harmonia Sintética",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
            },
            {
                "id": "AVN",
                "nome_no_mxd": "Área de vegetação nativa",
                "fonte": "local.AVN",
                "estilo": "avn",
                "ordem": 20,
            },
        ],
        "saidas": ["pdf", "png", "xlsx"],
        "saida": {"pasta": "Mapas", "nome_base": "Dinamica_2026_sintetico"},
    }
    fontes_idx = {"ATP": "SHP/ATP.shp", "AVN": "SHP/AVN.shp"}

    pdf_path, artefatos = gerar_pdf_minimo(mapspec, guard=guard, fontes_idx=fontes_idx)
    assert pdf_path.is_file()

    # Valida estrutura PDF via PyMuPDF
    doc = fitz.open(pdf_path)
    assert len(doc) == 1, "PDF deve ter exatamente 1 página"
    page = doc[0]
    rect = page.rect
    # A4 retrato: 595.28 x 841.89 pt (+-2pt)
    assert rect.width < rect.height, "PDF deveria ser orientação retrato"

    # Rasteriza a 150 dpi
    pix = page.get_pixmap(dpi=150)
    assert pix.width > 1000
    assert pix.height > 1500
    png_destino = tmp_path / "Dinamica_2026_sintetico_raster.png"
    pix.save(png_destino)
    assert png_destino.is_file()
    assert png_destino.stat().st_size > 50000, "Raster não pode ser imagem em branco"

    # Confere LayoutSpec nos artefatos
    assert "layout_spec" in artefatos
    assert artefatos["layout_spec"]["orientacao"] == "retrato"


def test_gerar_pdf_sintetico_paisagem_e_rasterizar(tmp_path: Path) -> None:
    """Gera PDF sintético paisagem (Tipologia), rasteriza e confere conformidade."""
    pasta_shp = tmp_path / "SHP"
    pasta_shp.mkdir()
    escrever_shapefile_quadrado_utm(pasta_shp / "ATP.shp", nome="Harmonia_Paisagem", lado_m=4000)

    guard = WorkspaceGuard(tmp_path)
    mapspec = {
        "titulo": "Tipologia Vegetal — Paisagem Sintético",
        "template": "tipologia_paisagem",
        "folha": {"formato": "A4", "orientacao": "paisagem"},
        "imovel": {"nome": "Fazenda Harmonia Sintética", "geometria": "local.ATP"},
        "camadas": [
            {
                "id": "ATP",
                "nome_no_mxd": "Fazenda Harmonia Sintética",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
            }
        ],
        "saidas": ["pdf", "png"],
        "saida": {"pasta": "Mapas", "nome_base": "Tipologia_sintetico"},
    }
    fontes_idx = {"ATP": "SHP/ATP.shp"}

    pdf_path, artefatos = gerar_pdf_minimo(mapspec, guard=guard, fontes_idx=fontes_idx)
    assert pdf_path.is_file()

    doc = fitz.open(pdf_path)
    assert len(doc) == 1
    page = doc[0]
    rect = page.rect
    # A4 paisagem: width > height
    assert rect.width > rect.height, "PDF deveria ser orientação paisagem"

    # Rasteriza a 150 dpi
    pix = page.get_pixmap(dpi=150)
    assert pix.width > 1500
    assert pix.height > 1000
    png_destino = tmp_path / "Tipologia_sintetico_raster.png"
    pix.save(png_destino)
    assert png_destino.is_file()
    assert png_destino.stat().st_size > 50000

    assert "layout_spec" in artefatos
    assert artefatos["layout_spec"]["orientacao"] == "paisagem"
