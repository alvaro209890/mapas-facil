# A13 / W11-12 — menor distância entre o imóvel e feições externas (TI/UC/embargo).
# Suporta projeção AEQD (Azimuthal Equidistant) e segregação de TI e zona de amortecimento.

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from mapasfacil_nucleo.geo.area import reprojetar
from mapasfacil_nucleo.geo.crs import epsg_utm_sirgas

_GEOGRAFICOS = frozenset({4326, 4674})


@dataclass(frozen=True)
class RelatorioDistanciaTI:
    """Relatório detalhado de distância à Terra Indígena e zona de amortecimento (W11-12)."""

    distancia_km: float
    status: str  # "sobrepoe", "zona_amortecimento", "afastado"
    em_zona_amortecimento: bool
    raio_amortecimento_km: float
    mensagem: str


def _obter_projecao_aeqd(centroide_geom: BaseGeometry, epsg_origem: int) -> pyproj.Transformer:
    """Cria transformer para projeção Azimutal Equidistante (AEQD) centrada no imóvel."""
    # Garante centroide em WGS84/SIRGAS2000 geográfico (lon, lat)
    c_geo = reprojetar(centroide_geom, epsg_origem, 4674)
    lon, lat = c_geo.x, c_geo.y
    crs_aeqd = pyproj.CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +ellps=GRS80 +units=m")
    crs_orig = pyproj.CRS.from_user_input(epsg_origem)
    return pyproj.Transformer.from_crs(crs_orig, crs_aeqd, always_xy=True)


def distancia_minima_km(
    geometria_referencia: BaseGeometry,
    epsg_referencia: int,
    geometrias_alvo: list[BaseGeometry],
    epsg_alvo: int,
    *,
    usar_aeqd: bool = True,
) -> float | None:
    """Menor distância (km) entre `geometria_referencia` e `geometrias_alvo`.

    Por padrão (W11-12), utiliza projeção AEQD centrada no centroide da referência,
    garantindo exatidão geodésica entre bordas. Se sobrepuser, retorna 0.0.
    """
    if not geometrias_alvo:
        return None

    ref = geometria_referencia if geometria_referencia.is_valid else geometria_referencia.buffer(0)
    alvos_validos = [g if g.is_valid else g.buffer(0) for g in geometrias_alvo if not g.is_empty]
    if not alvos_validos:
        return None

    alvo_unico = unary_union(alvos_validos)

    if usar_aeqd:
        transf_ref = _obter_projecao_aeqd(ref.centroid, epsg_referencia)
        crs_aeqd = transf_ref.target_crs
        transf_alvo = pyproj.Transformer.from_crs(
            pyproj.CRS.from_user_input(epsg_alvo), crs_aeqd, always_xy=True
        )

        ref_planar = transform(transf_ref.transform, ref)
        alvo_planar = transform(transf_alvo.transform, alvo_unico)
    else:
        # Modo UTM clássico
        epsg_calculo = (
            epsg_utm_sirgas(ref.centroid.x)
            if epsg_referencia in _GEOGRAFICOS
            else epsg_referencia
        )
        ref_planar = reprojetar(ref, epsg_referencia, epsg_calculo)
        alvo_planar = reprojetar(alvo_unico, epsg_alvo, epsg_calculo)

    distancia_m = float(ref_planar.distance(alvo_planar))
    return round(distancia_m / 1000.0, 3)


def avaliar_distancia_ti(
    geometria_imovel: BaseGeometry,
    epsg_imovel: int,
    geometrias_ti: list[BaseGeometry],
    epsg_ti: int,
    raio_amortecimento_km: float = 10.0,
) -> RelatorioDistanciaTI | None:
    """Avalia a distância à Terra Indígena separando a TI física e a Zona de Amortecimento (W11-12)."""
    d = distancia_minima_km(geometria_imovel, epsg_imovel, geometrias_ti, epsg_ti, usar_aeqd=True)
    if d is None:
        return None

    if d == 0.0:
        return RelatorioDistanciaTI(
            distancia_km=0.0,
            status="sobrepoe",
            em_zona_amortecimento=True,
            raio_amortecimento_km=raio_amortecimento_km,
            mensagem="O imóvel sobrepõe a Terra Indígena.",
        )
    elif d <= raio_amortecimento_km:
        return RelatorioDistanciaTI(
            distancia_km=d,
            status="zona_amortecimento",
            em_zona_amortecimento=True,
            raio_amortecimento_km=raio_amortecimento_km,
            mensagem=(
                f"O imóvel está a {d:.2f} km da Terra Indígena "
                f"(dentro da zona de amortecimento de {raio_amortecimento_km:.0f} km)."
            ),
        )
    else:
        return RelatorioDistanciaTI(
            distancia_km=d,
            status="afastado",
            em_zona_amortecimento=False,
            raio_amortecimento_km=raio_amortecimento_km,
            mensagem=(
                f"O imóvel está a {d:.2f} km da Terra Indígena "
                f"(fora da zona de amortecimento de {raio_amortecimento_km:.0f} km)."
            ),
        )
