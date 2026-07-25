from __future__ import annotations

from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from mapasfacil_nucleo.geo.crs import epsg_utm_sirgas

_GEOGRAFICOS = frozenset({4326, 4674})


def _reprojetar(geometria: BaseGeometry, epsg_origem: int, epsg_destino: int) -> BaseGeometry:
    from pyproj import Transformer

    transformer = Transformer.from_crs(
        f"EPSG:{epsg_origem}",
        f"EPSG:{epsg_destino}",
        always_xy=True,
    )
    return transform(transformer.transform, geometria)


def area_hectares(
    geometrias: list[BaseGeometry],
    *,
    epsg_origem: int,
    longitude_centroide: float,
) -> tuple[float, int]:
    """Área total em hectares (4 casas) e contagem de geometrias corrigidas."""
    if not geometrias:
        return 0.0, 0

    if epsg_origem not in _GEOGRAFICOS and epsg_origem < 31900:
        raise ValueError(f"CRS não projetado suportado para área: EPSG:{epsg_origem}")

    epsg_calculo = epsg_origem
    if epsg_origem in _GEOGRAFICOS:
        epsg_calculo = epsg_utm_sirgas(longitude_centroide)

    corrigidas = 0
    partes: list[BaseGeometry] = []
    for geom in geometrias:
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
            corrigidas += 1
        if epsg_origem != epsg_calculo:
            geom = _reprojetar(geom, epsg_origem, epsg_calculo)
        partes.append(geom)

    if not partes:
        return 0.0, corrigidas

    area_m2 = float(unary_union(partes).area)
    return round(area_m2 / 10_000, 4), corrigidas
