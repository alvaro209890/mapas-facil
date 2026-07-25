from __future__ import annotations

from pathlib import Path

import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace.indice import varrer
from mapasfacil_nucleo.workspace.papeis import detectar_papel
from mapasfacil_nucleo.workspace.shapefile import inspecionar


@pytest.fixture
def simcar_03() -> Path:
    caminho = (
        raiz_repositorio()
        / "Referencias_IMAP/Mapas/03/Arquivo Processado (11)"
    ).resolve()
    if not caminho.is_dir():
        pytest.skip("Acervo Mapas/03 não disponível neste clone.")
    return caminho


def test_simcar_papeis_principais(simcar_03: Path) -> None:
    assert detectar_papel("ATP.shp") == "ATP"
    assert detectar_papel("AREA_CONSOLIDADA.shp") == "AC"
    assert detectar_papel("AUAS.shp") == "AUAS"
    assert detectar_papel("TIPOLOGIA_VEGETAL.shp") == "TIPOLOGIA"
    assert detectar_papel("MANGUEZAL.shp") == "HIDRO_POLIGONO"


def test_simcar_atp_area(simcar_03: Path) -> None:
    meta = inspecionar(simcar_03 / "ATP.shp")
    assert meta.feicoes == 1
    assert meta.area_ha is not None
    assert meta.area_ha == pytest.approx(64.4229, rel=0.002)


def test_simcar_camadas_vazias_nao_invalidam(simcar_03: Path) -> None:
    for nome in ("AUAS.shp", "MANGUEZAL.shp", "VEREDA.shp"):
        meta = inspecionar(simcar_03 / nome)
        assert meta.vazia is True
        assert meta.valido is True
        assert meta.feicoes == 0


def test_simcar_indexacao_completa(simcar_03: Path) -> None:
    idx = varrer(simcar_03)
    assert len(idx["shapefiles"]) == 37
    vazios = [s for s in idx["shapefiles"] if s["vazia"]]
    assert len(vazios) >= 10
    atp = next(s for s in idx["shapefiles"] if s["papel"] == "ATP")
    assert atp["feicoes"] == 1


def test_workspace_abrir_simcar_03(simcar_03: Path) -> None:
    raiz = simcar_03.parent
    resultado = workspace_servico.abrir(str(raiz))
    shps = resultado["workspace"]["shapefiles"]
    assert any(s["papel"] == "ATP" for s in shps)
    assert any(s["papel"] == "AUAS" and s["vazia"] for s in shps)
