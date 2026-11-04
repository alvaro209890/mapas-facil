"""Utilitários de CRS (Sistemas de Coordenadas de Referência) — W11-03 e W4-10.

Suporta zonas UTM 20S, 21S e 22S no SIRGAS 2000 e transformação oficial
SAD69 (EPSG:4618) -> SIRGAS 2000 (EPSG:4674) via parâmetros Helmert IBGE (Res. 1/2005).
"""

from __future__ import annotations

import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform


def zona_utm_por_longitude(longitude: float) -> int:
    """Zona UTM SIRGAS 2000 para Mato Grosso e centro-oeste brasileiro (W11-03).

    - longitude < -60.0° → zona 20S (extremo oeste de MT / RO)
    - -60.0° <= longitude < -54.0° → zona 21S (centro e norte de MT)
    - longitude >= -54.0° → zona 22S (leste de MT, Vale do Araguaia)
    """
    if longitude < -60.0:
        return 20
    if longitude < -54.0:
        return 21
    return 22


def epsg_utm_sirgas(longitude: float) -> int:
    """Retorna o código EPSG UTM SIRGAS 2000 correspondente (31980, 31981 ou 31982)."""
    zona = zona_utm_por_longitude(longitude)
    return 31960 + zona  # 31980 = 20S, 31981 = 21S, 31982 = 22S


def crs_por_zona(zona: int) -> str:
    """Retorna a string EPSG correspondente à zona UTM SIRGAS 2000."""
    return f"EPSG:{31960 + zona}"


def converter_sad69_para_sirgas2000(geometria: BaseGeometry, epsg_origem: int = 4618) -> BaseGeometry:
    """Converte geometria de SAD69 para SIRGAS 2000 usando parâmetros Helmert do IBGE (W4-10).

    Deslocamento geodésico aproximado: ~65 m no Brasil central.
    """
    crs_sad69 = pyproj.CRS.from_proj4(
        "+proj=longlat +ellps=aust_SA +towgs84=-67.35,4.69,-60.39,0,0,0,0 +no_defs"
    )
    crs_sirgas = pyproj.CRS.from_epsg(4674)
    transformer = pyproj.Transformer.from_crs(crs_sad69, crs_sirgas, always_xy=True)
    return transform(transformer.transform, geometria)
