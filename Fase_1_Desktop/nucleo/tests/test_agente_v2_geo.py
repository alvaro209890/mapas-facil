import os
import shutil
import tempfile
from pathlib import Path
import pytest
import shapefile

from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_geo import registrar_tools_geo
from mapasfacil_nucleo.protocolo import Emissor


@pytest.fixture
def ws_geo():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_geo_")
    ws_path = Path(temp_dir)
    shp_dir = ws_path / "SHP"
    shp_dir.mkdir(parents=True)

    # Criar um shapefile poligonal de teste em SIRGAS 2000 UTM 21S (EPSG:31981)
    # Coordenadas UTM aproximadas para um quadrado de 1000m x 1000m = 1.000.000 m² = 100 ha
    shp_quadrado = shp_dir / "quadrado.shp"
    with shapefile.Writer(str(shp_quadrado), shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=50)
        w.field("TIPO", "C", size=20)
        # Anel externo clockwise
        w.poly([[[500000, 8500000], [501000, 8500000], [501000, 8501000], [500000, 8501000], [500000, 8500000]]])
        w.record("Gleba 1", "Imovel")

    # .prj para EPSG:31981
    prj_31981 = (
        'PROJCS["SIRGAS 2000 / UTM zone 21S",GEOGCS["SIRGAS 2000",'
        'DATUM["Sistema_de_Referencia_Geocentrico_para_las_AmericaS_2000",'
        'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],'
        'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
        'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-57],'
        'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],'
        'PARAMETER["false_northing",10000000],UNIT["metre",1]]'
    )
    (shp_dir / "quadrado.prj").write_text(prj_31981, encoding="utf-8")

    # Criar uma máscara que cobre metade do quadrado: 500m x 1000m = 50 ha
    shp_mascara = shp_dir / "mascara.shp"
    with shapefile.Writer(str(shp_mascara), shapeType=shapefile.POLYGON) as w:
        w.field("ID", "N")
        w.poly([[[500000, 8500000], [500500, 8500000], [500500, 8501000], [500000, 8501000], [500000, 8500000]]])
        w.record(1)
    (shp_dir / "mascara.prj").write_text(prj_31981, encoding="utf-8")

    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_geo_inspecionar(ws_geo):
    registro = RegistroFerramentas()
    registrar_tools_geo(registro)

    ctx = {"workspace": ws_geo}
    res = registro.executar("geo_inspecionar", {"caminho": "SHP/quadrado.shp"}, ctx)

    assert res["ok"] is True
    assert res["total_feicoes"] == 1
    assert "NOME" in [c["nome"] for c in res["campos"]]
    assert res["bbox"][0] == 500000
    assert res["bbox"][1] == 8500000


def test_geo_area(ws_geo):
    registro = RegistroFerramentas()
    registrar_tools_geo(registro)

    ctx = {"workspace": ws_geo}
    res = registro.executar("geo_area", {"caminho": "SHP/quadrado.shp", "unidade": "ha"}, ctx)

    assert res["ok"] is True
    # 1000m x 1000m = 100 hectares
    assert pytest.approx(res["area_total"], 0.1) == 100.0


def test_geo_recortar(ws_geo):
    registro = RegistroFerramentas()
    registrar_tools_geo(registro)

    ctx = {"workspace": ws_geo}
    res = registro.executar(
        "geo_recortar",
        {
            "camada_entrada": "SHP/quadrado.shp",
            "camada_mascara": "SHP/mascara.shp",
            "camada_saida": "SHP/recortado.shp",
        },
        ctx,
    )

    assert res["ok"] is True
    assert (ws_geo / "SHP" / "recortado.shp").exists()

    # Área recortada deve ser ~50 ha
    res_area = registro.executar("geo_area", {"caminho": "SHP/recortado.shp", "unidade": "ha"}, ctx)
    assert pytest.approx(res_area["area_total"], 0.1) == 50.0


def test_geo_reprojetar(ws_geo):
    registro = RegistroFerramentas()
    registrar_tools_geo(registro)

    ctx = {"workspace": ws_geo}
    # Reprojetar para SIRGAS 2000 Geográficas (EPSG:4674)
    res = registro.executar(
        "geo_reprojetar",
        {
            "camada_entrada": "SHP/quadrado.shp",
            "camada_saida": "SHP/quadrado_geo.shp",
            "epsg_destino": 4674,
        },
        ctx,
    )

    assert res["ok"] is True
    assert (ws_geo / "SHP" / "quadrado_geo.shp").exists()
    assert (ws_geo / "SHP" / "quadrado_geo.prj").exists()

    res_insp = registro.executar("geo_inspecionar", {"caminho": "SHP/quadrado_geo.shp"}, ctx)
    assert res_insp["ok"] is True
    # Longitudes em graus devem estar em torno de -57
    assert -60.0 < res_insp["bbox"][0] < -50.0
