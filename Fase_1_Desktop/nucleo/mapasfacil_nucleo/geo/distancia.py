# A13 — menor distância entre o imóvel e um conjunto de feições externas
# (TI/UC/embargo — tool `distancia_ate`, F1-03 §Estrutura `geo/distancia.py`).

from __future__ import annotations

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mapasfacil_nucleo.geo.area import reprojetar
from mapasfacil_nucleo.geo.crs import epsg_utm_sirgas

_GEOGRAFICOS = frozenset({4326, 4674})


def _epsg_planar(epsg_origem: int, longitude_centroide: float) -> int:
    if epsg_origem in _GEOGRAFICOS:
        return epsg_utm_sirgas(longitude_centroide)
    return epsg_origem


def distancia_minima_km(
    geometria_referencia: BaseGeometry,
    epsg_referencia: int,
    geometrias_alvo: list[BaseGeometry],
    epsg_alvo: int,
) -> float | None:
    """Menor distância (km) entre `geometria_referencia` (ex.: ATP) e `geometrias_alvo`.

    Reprojeta ambas para a UTM SIRGAS 2000 do centroide de referência (métrica) antes
    de medir. `None` se `geometrias_alvo` estiver vazio.
    """
    if not geometrias_alvo:
        return None

    ref = geometria_referencia if geometria_referencia.is_valid else geometria_referencia.buffer(0)
    epsg_calculo = _epsg_planar(epsg_referencia, ref.centroid.x)

    ref_planar = reprojetar(ref, epsg_referencia, epsg_calculo)

    alvos_validos = [g if g.is_valid else g.buffer(0) for g in geometrias_alvo if not g.is_empty]
    if not alvos_validos:
        return None
    alvo_unico = unary_union(alvos_validos)
    alvo_planar = reprojetar(alvo_unico, epsg_alvo, epsg_calculo)

    distancia_m = float(ref_planar.distance(alvo_planar))
    return round(distancia_m / 1000, 3)
