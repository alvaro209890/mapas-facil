"""Calculo do retangulo e linha-guia do minimapa em coordenada de pagina.

Espelho do que `ferramentas/mudar_municipio_minimapa_arcpy.py` aplica via ArcPy.
Usado pelo motor nativo (F1-05) e pelo payload `graficos` do `arcpy_job`.
"""

from __future__ import annotations

from dataclasses import dataclass


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

    # A4 retrato (mm, Y do topo)
    mapa: RetanguloPagina = RetanguloPagina(7.0, 5.0, 203.5, 257.0)
    minimapa: RetanguloPagina = RetanguloPagina(0.0, 262.0, 62.0, 297.0)
    # tamanho tipico do quadradinho vermelho (mm)
    lado_retangulo_mm: float = 3.5


def map_xy_para_pagina_mm(
    *,
    map_x: float,
    map_y: float,
    extent: tuple[float, float, float, float],
    caixa_minimapa: RetanguloPagina,
) -> tuple[float, float]:
    """Converte XY do data frame MINIMAPA → mm de pagina (Y do topo).

    `extent` = (xmin, ymin, xmax, ymax) no CRS do minimapa.
    No layout ArcMap a origem do elemento e canto inferior-esquerdo; aqui a
    convencao do manifesto Harmonia e Y do topo — o chamador converte se precisar.
    """
    xmin, ymin, xmax, ymax = extent
    w = (xmax - xmin) or 1.0
    h = (ymax - ymin) or 1.0
    # fracao no data frame (origem inferior-esquerda do DF)
    fx = (map_x - xmin) / w
    fy = (map_y - ymin) / h
    # caixa_minimapa em Y-do-topo: y0=topo, y1=base
    page_x = caixa_minimapa.x0 + fx * (caixa_minimapa.x1 - caixa_minimapa.x0)
    # fy=0 → base do minimapa (y1); fy=1 → topo do minimapa (y0)
    page_y = caixa_minimapa.y1 - fy * (caixa_minimapa.y1 - caixa_minimapa.y0)
    return page_x, page_y


def retangulo_e_guia_L(
    *,
    centro_page_mm: tuple[float, float],
    layout: MiniMapaLayout | None = None,
    lado_mm: float | None = None,
) -> dict:
    """Calcula posicao do quadradinho vermelho e da linha-guia em L.

    A linha em L sai do canto superior-direito do retangulo e sobe/esquerda ate
    o canto inferior-esquerdo do quadro do MAPA — como nos PDFs de Mapas/01.
    """
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
    # origem L: topo-direita do retangulo (Y do topo → menor y = mais acima)
    ox, oy = ret["x1"], ret["y0"]
    # alvo: canto inferior-esquerdo interno do MAPA
    tx = layout.mapa.x0 + 1.5
    ty = layout.mapa.y1  # base do quadro
    # polilinha em L: (ox,oy) → (tx,oy) → (tx,ty)  se ox>tx; senao vertical primeiro
    if abs(ox - tx) < 0.01:
        pontos = [(ox, oy), (tx, ty)]
    else:
        pontos = [(ox, oy), (tx, oy), (tx, ty)]
    return {
        "retangulo_mm": ret,
        "guia_L_mm": pontos,
        # payload compatível com arcpy_job (cm, origem inferior-esquerda A4=297mm)
        "graficos_arcpy_cm": {
            "MINIMAPA_RETANGULO": {
                "x": ret["x0"] / 10.0,
                # ArcMap Y: 0 = base da pagina
                "y": (297.0 - ret["y1"]) / 10.0,
            },
            "MINIMAPA_GUIA": {
                "x": min(p[0] for p in pontos) / 10.0,
                "y": (297.0 - max(p[1] for p in pontos)) / 10.0,
                "width_cm": (max(p[0] for p in pontos) - min(p[0] for p in pontos)) / 10.0,
                "height_cm": (max(p[1] for p in pontos) - min(p[1] for p in pontos)) / 10.0,
            },
        },
    }
