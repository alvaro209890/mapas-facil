from __future__ import annotations

from pathlib import Path

from PIL import Image

from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.quantitativos.calcular import calcular as calcular_quantitativos
from mapasfacil_nucleo.quantitativos.png_tabela import renderizar_png_tabela
from tests.helpers_fixtures import montar_workspace_minimo


def test_renderizar_png_tabela_dpi_e_dimensoes(tmp_path: Path) -> None:
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
        "tabela": {
            "colunas": [
                "Propriedade",
                "Área total da propriedade (ha)",
                "Área de vegetação nativa (ha)",
            ],
            "total_geral": True,
            "casas_decimais": 4,
        },
    }
    dados = calcular_quantitativos(mapspec, guard=guard, fontes_idx=fontes_idx)
    destino = tmp_path / "Mapas" / "recursos" / "tabela_quantitativos.png"
    meta = renderizar_png_tabela(dados, destino)

    assert destino.exists()
    assert meta["ok_dpi"] is True
    assert meta["dpi_efetivo"] >= 600
    assert meta["largura_px"] >= 1800

    img = Image.open(destino)
    assert img.size == (meta["largura_px"], meta["altura_px"])
    assert img.format == "PNG"


def test_gerar_mapa_produz_png_tabela(tmp_path: Path, repo_root: Path) -> None:
    import copy
    import json

    montar_workspace_minimo(tmp_path)
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    mapspec = copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8")))
    mapspec["camadas"] = [c for c in mapspec["camadas"] if c["fonte"].startswith("local.")]
    mapspec["saidas"] = ["pdf", "png"]
    mapspec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "Dinamica_png",
        "materializar_camadas_em": "SHP",
    }

    fontes_idx = {
        "ATP": "dados/ATP.shp",
        "AVN": "dados/AVN.shp",
        "AUAS": "dados/AUAS.shp",
    }
    guard = WorkspaceGuard(tmp_path)
    resultado = gerar_mapa(mapspec, guard, fontes_idx)
    assert "png_tabela" in resultado
    png = tmp_path / resultado["png_tabela"]
    assert png.exists()
    assert png.name == "tabela_quantitativos.png"
