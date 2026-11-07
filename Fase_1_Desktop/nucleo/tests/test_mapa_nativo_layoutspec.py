"""Testes de consumo de LayoutSpec pelo motor nativo (PDF-first)."""

from __future__ import annotations

from pathlib import Path
import pytest

from mapasfacil_nucleo.layout import de_perfil, validar
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo, _perfil_do_mapspec
from mapasfacil_nucleo.motores.perfil_pagina import RETRATO, Caixa
from mapasfacil_nucleo.fsguard import WorkspaceGuard


def test_perfil_do_mapspec_com_layout_spec_explicito() -> None:
    custom_spec = de_perfil(RETRATO, id="custom_01", nome="Customizado").para_dict()
    # Modifica a caixa do título para uma posição bem específica
    custom_spec["elementos"]["titulo"] = {"x0": 50.0, "y0": 10.0, "x1": 150.0, "y1": 25.0}

    mapspec = {
        "titulo": "Teste Layout Custom",
        "template": "dinamica_retrato",
        "layout_spec": custom_spec,
    }

    perfil = _perfil_do_mapspec(mapspec)
    assert perfil.id == "custom_01"
    assert perfil.titulo.x0 == 50.0
    assert perfil.titulo.y0 == 10.0
    assert perfil.titulo.x1 == 150.0
    assert perfil.titulo.y1 == 25.0


def test_gerar_pdf_minimo_emite_layout_spec_valido(tmp_path: Path) -> None:
    # Monta mapspec mínimo sintético
    from tests.helpers_fixtures import escrever_shapefile_quadrado_utm

    pasta_shp = tmp_path / "SHP"
    pasta_shp.mkdir()
    atp_shp = pasta_shp / "ATP.shp"
    escrever_shapefile_quadrado_utm(atp_shp)

    guard = WorkspaceGuard(tmp_path)
    mapspec = {
        "titulo": "Dinâmica 2026 Teste",
        "template": "serie_dinamica_2026",
        "folha": {"formato": "A4", "orientacao": "retrato"},
        "imovel": {"nome": "Fazenda Modelo", "geometria": "local.ATP"},
        "camadas": [
            {
                "id": "ATP",
                "nome_no_mxd": "Fazenda Modelo",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
            }
        ],
        "saidas": ["pdf"],
    }
    fontes_idx = {"ATP": "SHP/ATP.shp"}

    pdf_path, artefatos = gerar_pdf_minimo(
        mapspec,
        guard=guard,
        fontes_idx=fontes_idx,
    )

    assert pdf_path.is_file()
    assert "layout_spec" in artefatos
    spec_dict = artefatos["layout_spec"]
    val = validar(spec_dict)
    assert val["valido"] is True
    assert spec_dict["orientacao"] == "retrato"
