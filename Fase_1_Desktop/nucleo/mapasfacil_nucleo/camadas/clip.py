# A13 — bbox → clip fino local (planos/03-wfs-e-servicos-geo.md §BBOX vs INTERSECTS).
#
# Pipeline documentado (custou um bug real no GeoForest — INTERSECTS do GeoServer
# perdeu 27 de 75 feições em imóvel grande): buscar por BBOX expandido, depois
# recortar fino localmente. Aqui o recorte fino é geométrico (shapely), não outra
# ida à rede.

from __future__ import annotations

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

BBox = tuple[float, float, float, float]

FATOR_EXPANSAO_PADRAO = 0.25
MINIMO_GRAUS = 0.002


def expandir_bbox(
    bbox: BBox,
    *,
    fator: float = FATOR_EXPANSAO_PADRAO,
    minimo: float = MINIMO_GRAUS,
) -> BBox:
    """Expande ~25% (mín. 0,002°) — pega vizinhos na moldura antes do recorte fino."""
    xmin, ymin, xmax, ymax = bbox
    largura = xmax - xmin
    altura = ymax - ymin
    folga_x = max(largura * fator, minimo)
    folga_y = max(altura * fator, minimo)
    return (xmin - folga_x, ymin - folga_y, xmax + folga_x, ymax + folga_y)


def bbox_geometria(geometria: BaseGeometry) -> BBox:
    return tuple(geometria.bounds)  # type: ignore[return-value]


def clip_bbox_pares(
    pares: list[tuple[BaseGeometry, dict]], bbox: BBox
) -> list[tuple[BaseGeometry, dict]]:
    """Como `clip_bbox`, mas carregando os atributos junto.

    Existe porque camada temática se pinta **por classe** (Floresta × Cerrado na
    Tipologia, ano do desmate no PRODES): perder o atributo no recorte obriga a
    ir à rede de novo só para saber de que cor é cada polígono.
    """
    retangulo = box(*bbox)
    recortados: list[tuple[BaseGeometry, dict]] = []
    for geom, props in pares:
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        intersecao = geom.intersection(retangulo)
        if not intersecao.is_empty:
            recortados.append((intersecao, props))
    return recortados


def clip_bbox(geometrias: list[BaseGeometry], bbox: BBox) -> list[BaseGeometry]:
    """Recorte fino contra o retângulo do bbox — descarta o que ficou só na moldura."""
    return [g for g, _ in clip_bbox_pares([(g, {}) for g in geometrias], bbox)]


def clip_poligono(geometrias: list[BaseGeometry], poligono: BaseGeometry) -> list[BaseGeometry]:
    """Recorte fino pelo polígono exato do imóvel (não só o bbox)."""
    alvo = poligono if poligono.is_valid else poligono.buffer(0)
    recortadas: list[BaseGeometry] = []
    for geom in geometrias:
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        intersecao = geom.intersection(alvo)
        if not intersecao.is_empty:
            recortadas.append(intersecao)
    return recortadas
