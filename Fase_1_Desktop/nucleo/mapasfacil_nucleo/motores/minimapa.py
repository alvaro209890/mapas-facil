"""Calculo do retangulo e linha-guia do minimapa em coordenada de pagina.

Espelho do que `ferramentas/mudar_municipio_minimapa_arcpy.py` aplica via ArcPy.
Usado pelo motor nativo (F1-05) e pelo payload `graficos` do `arcpy_job`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyproj import Transformer


@dataclass(frozen=True)
class RetanguloPagina:
    """Retangulo em mm (origem topo-esquerda da pagina A4, eixo Y para baixo)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def centro(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)


@dataclass(frozen=True)
class MiniMapaLayout:
    """Caixas medidas do padrao Harmonia (planos/01-padrao-imap-harmonia.md)."""

    mapa: RetanguloPagina = RetanguloPagina(7.0, 5.0, 203.5, 257.0)
    minimapa: RetanguloPagina = RetanguloPagina(0.0, 262.0, 62.0, 297.0)
    lado_retangulo_mm: float = 3.5
    altura_pagina_mm: float = 297.0


def map_xy_para_pagina_mm(
    *,
    map_x: float,
    map_y: float,
    extent: tuple[float, float, float, float],
    caixa_minimapa: RetanguloPagina,
) -> tuple[float, float]:
    """Converte XY do data frame MINIMAPA → mm de pagina (Y do topo)."""
    xmin, ymin, xmax, ymax = extent
    w = (xmax - xmin) or 1.0
    h = (ymax - ymin) or 1.0
    fx = (map_x - xmin) / w
    fy = (map_y - ymin) / h
    page_x = caixa_minimapa.x0 + fx * (caixa_minimapa.x1 - caixa_minimapa.x0)
    page_y = caixa_minimapa.y1 - fy * (caixa_minimapa.y1 - caixa_minimapa.y0)
    return page_x, page_y


def retangulo_e_guia_L(
    *,
    centro_page_mm: tuple[float, float],
    layout: MiniMapaLayout | None = None,
    lado_mm: float | None = None,
) -> dict[str, Any]:
    """Calcula posicao do quadradinho vermelho e da linha-guia em L."""
    layout = layout or MiniMapaLayout()
    lado = lado_mm if lado_mm is not None else layout.lado_retangulo_mm
    cx, cy = centro_page_mm
    half = lado / 2.0
    ret = {
        "x0": cx - half,
        "y0": cy - half,
        "x1": cx + half,
        "y1": cy + half,
    }
    ox, oy = ret["x1"], ret["y0"]
    tx = layout.mapa.x0 + 1.5
    ty = layout.mapa.y1
    if abs(ox - tx) < 0.01:
        pontos: list[tuple[float, float]] = [(ox, oy), (tx, ty)]
    else:
        pontos = [(ox, oy), (tx, oy), (tx, ty)]
    h_pag = layout.altura_pagina_mm
    return {
        "retangulo_mm": ret,
        "guia_L_mm": pontos,
        "graficos_arcpy_cm": {
            "MINIMAPA_RETANGULO": {
                "x": ret["x0"] / 10.0,
                "y": (h_pag - ret["y1"]) / 10.0,
            },
            "MINIMAPA_GUIA": {
                "x": min(p[0] for p in pontos) / 10.0,
                "y": (h_pag - max(p[1] for p in pontos)) / 10.0,
                "width_cm": (max(p[0] for p in pontos) - min(p[0] for p in pontos)) / 10.0,
                "height_cm": (max(p[1] for p in pontos) - min(p[1] for p in pontos)) / 10.0,
            },
        },
    }


def graficos_para_centroide(
    *,
    lon: float,
    lat: float,
    extent_minimapa_wgs84: tuple[float, float, float, float],
    layout: MiniMapaLayout | None = None,
    epsg_minimapa: int = 3857,
) -> dict[str, Any]:
    """Centroide WGS84 + extent do minimapa → payload `graficos` do arcpy_job."""
    layout = layout or MiniMapaLayout()
    to_df = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg_minimapa}", always_xy=True)
    mx, my = to_df.transform(lon, lat)
    x0, y0, x1, y1 = extent_minimapa_wgs84
    corners = [
        to_df.transform(x0, y0),
        to_df.transform(x0, y1),
        to_df.transform(x1, y0),
        to_df.transform(x1, y1),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    extent_df = (min(xs), min(ys), max(xs), max(ys))
    page = map_xy_para_pagina_mm(
        map_x=mx,
        map_y=my,
        extent=extent_df,
        caixa_minimapa=layout.minimapa,
    )
    calc = retangulo_e_guia_L(centro_page_mm=page, layout=layout)
    calc["centro_page_mm"] = page
    calc["extent_minimapa_df"] = extent_df
    calc["ponto_df"] = (mx, my)
    return calc
