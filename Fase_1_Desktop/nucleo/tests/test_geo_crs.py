# Testes de CRS: zonas UTM 20S/21S/22S (W11-03) e conversão SAD69 -> SIRGAS2000 (W4-10).

import pytest
from shapely.geometry import Point
from mapasfacil_nucleo.geo.crs import (
    converter_sad69_para_sirgas2000,
    crs_por_zona,
    epsg_utm_sirgas,
    zona_utm_por_longitude,
)


def test_zonas_utm_por_longitude() -> None:
    # Zona 20S (extremo oeste de MT, RO)
    assert zona_utm_por_longitude(-60.5) == 20
    assert epsg_utm_sirgas(-60.5) == 31980
    assert crs_por_zona(20) == "EPSG:31980"

    # Zona 21S (centro de MT)
    assert zona_utm_por_longitude(-56.0) == 21
    assert epsg_utm_sirgas(-56.0) == 31981
    assert crs_por_zona(21) == "EPSG:31981"

    # Zona 22S (leste de MT, Querência)
    assert zona_utm_por_longitude(-52.0) == 22
    assert epsg_utm_sirgas(-52.0) == 31982
    assert crs_por_zona(22) == "EPSG:31982"


def test_converter_sad69_para_sirgas2000() -> None:
    # Ponto em Querência-MT em SAD69 geográfico (lon, lat)
    pt_sad69 = Point(-52.18, -12.35)
    pt_sirgas = converter_sad69_para_sirgas2000(pt_sad69)

    # Verifica deslocamento geodésico na ordem de ~65 m (~0.0006 graus)
    d_lon = abs(pt_sirgas.x - pt_sad69.x)
    d_lat = abs(pt_sirgas.y - pt_sad69.y)

    assert d_lon > 0.0001
    assert d_lat > 0.0001
    assert d_lon < 0.005
    assert d_lat < 0.005
