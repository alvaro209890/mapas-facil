from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mapasfacil_nucleo.geo.crs import epsg_utm_sirgas, zona_utm_por_longitude
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace.papeis import detectar_papel
from mapasfacil_nucleo.workspace.recibo_car import parsear
from mapasfacil_nucleo.workspace.shapefile import inspecionar
from tests.helpers_fixtures import (
    escrever_recibo_car_pdf,
    escrever_shapefile_geografico,
    escrever_shapefile_quadrado_utm,
    montar_workspace_minimo,
)


def test_zona_utm_por_longitude() -> None:
    assert zona_utm_por_longitude(-54.5) == 21
    assert zona_utm_por_longitude(-53.5) == 22
    assert zona_utm_por_longitude(-54.0) == 22


def test_epsg_utm_sirgas() -> None:
    assert epsg_utm_sirgas(-54.5) == 31981
    assert epsg_utm_sirgas(-53.5) == 31982


def test_area_quadrado_utm(tmp_path: Path) -> None:
    shp = escrever_shapefile_quadrado_utm(tmp_path / "q.shp", lado_m=1000)
    meta = inspecionar(shp)
    assert meta.area_ha == 100.0


def test_area_geografico_para_utm(tmp_path: Path) -> None:
    shp = escrever_shapefile_geografico(tmp_path / "geo.shp", lon=-53.5, lat=-10.0, delta=0.01)
    meta = inspecionar(shp)
    assert meta.area_ha is not None
    assert meta.area_ha > 0


def test_detectar_papeis() -> None:
    assert detectar_papel("ATP.shp") == "ATP"
    assert detectar_papel("AREA_CONSOLIDADA.shp") == "AC"
    assert detectar_papel("desconhecido.shp") is None


def test_workspace_abrir(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    resultado = workspace_servico.abrir(str(tmp_path))
    ws = resultado["workspace"]
    assert resultado["recibo"]["nome_imovel"] == "Fazenda Harmonia"
    assert resultado["recibo"]["car_estadual"] == "MT102042/2017"
    assert "cpf" not in resultado["recibo"]
    assert "ATP" in ws["fontes_locais"]
    assert ws["recibo_car"] is not None


def test_workspace_inspecionar_shapefile(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    info = workspace_servico.inspecionar("dados/ATP.shp")
    assert info["tipo"] == "shapefile"
    assert info["papel"] == "ATP"
    assert info["area_ha"] == 100.0


def test_recibo_rotulo_quebrado(tmp_path: Path) -> None:
    pdf = escrever_recibo_car_pdf(tmp_path / "recibo.pdf")
    dados = parsear(pdf)
    assert dados.documentos
    assert dados.documentos[0].tipo in {"Matrícula", "Posse"}
    assert "cpf" not in dados.para_dict()


def test_recibo_sem_cpf_na_saida(tmp_path: Path) -> None:
    pdf = escrever_recibo_car_pdf(tmp_path / "recibo.pdf")
    texto = json.dumps(parsear(pdf).para_dict(), ensure_ascii=False)
    assert "123.456.789" not in texto
    assert "cpf" not in texto.lower()


def test_recibo_pdf_corrompido(tmp_path: Path) -> None:
    ruim = tmp_path / "ruim.pdf"
    ruim.write_bytes(b"nao-e-pdf")
    from mapasfacil_nucleo.erros import ErroNucleo

    with pytest.raises(ErroNucleo, match="NU-030"):
        parsear(ruim)
