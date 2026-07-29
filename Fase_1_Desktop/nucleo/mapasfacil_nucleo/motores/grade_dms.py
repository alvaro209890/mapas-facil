"""Grade geográfica DMS do padrão Harmonia (planos/01 §Grade DMS).

Regras que este módulo implementa, todas medidas dos PDFs-modelo:

- rótulo `52°11'10"W` / `9°43'50"S` — **sem** zero à esquerda, hemisfério como
  letra sufixa, nunca sinal negativo;
- 4 a 8 rótulos por eixo, com passo em valor redondo de minutos/segundos;
- a grade é sempre **geográfica** (SIRGAS 2000), mesmo com o data frame em UTM
  ou Web Mercator — por isso os ticks nascem em graus e são projetados para a
  coordenada do eixo, e não o contrário.
"""

from __future__ import annotations

import math

import numpy as np
from pyproj import Transformer

PASSOS_SEGUNDOS: tuple[int, ...] = (
    5,
    10,
    15,
    20,
    30,
    60,  # 1'
    70,  # 1'10"
    90,  # 1'30"
    110,  # 1'50"
    120,  # 2'
    150,  # 2'30"
    180,  # 3'
    300,  # 5'
    600,  # 10'
    900,  # 15'
    1800,  # 30'
    3600,  # 1°
)
"""Passos aceitos, incluindo os três observados no acervo (1'50", 1'10", 1'0")."""

ALVO_MIN = 4
ALVO_MAX = 8
ALVO_IDEAL = 5.5

AMOSTRAS = 240
"""Pontos por meridiano/paralelo ao procurar o cruzamento com a borda."""


def escolher_passo(span_graus: float) -> int:
    """Passo em segundos que rende de 4 a 8 rótulos no intervalo."""
    span_seg = max(abs(span_graus) * 3600.0, 1e-9)
    melhor = PASSOS_SEGUNDOS[-1]
    melhor_custo = math.inf
    for passo in PASSOS_SEGUNDOS:
        n = span_seg / passo
        if n < 2:
            continue
        dentro = ALVO_MIN <= n <= ALVO_MAX
        # Fora da faixa alvo o custo explode, mas nunca vira infinito: extensões
        # muito pequenas ou muito grandes ainda precisam de algum passo.
        custo = abs(n - ALVO_IDEAL) + (0.0 if dentro else 100.0)
        if custo < melhor_custo:
            melhor_custo = custo
            melhor = passo
    return melhor


def valores_ticks(minimo: float, maximo: float, passo_segundos: int) -> list[float]:
    """Múltiplos do passo dentro do intervalo, em graus decimais."""
    passo = passo_segundos / 3600.0
    if passo <= 0:
        return []
    inicio = math.ceil(minimo / passo) * passo
    valores: list[float] = []
    atual = inicio
    # Tolerância de meio passo/1000 evita perder um tick por erro de ponto flutuante.
    while atual <= maximo + passo * 1e-3:
        valores.append(round(atual, 9))
        atual += passo
    return valores


def formatar(valor_graus: float, *, eixo: str) -> str:
    """`-52.186…, eixo="x"` → `52°11'10"W`."""
    hemisferio = ("W" if valor_graus < 0 else "E") if eixo == "x" else ("S" if valor_graus < 0 else "N")
    total_seg = round(abs(valor_graus) * 3600.0)
    graus, resto = divmod(total_seg, 3600)
    minutos, segundos = divmod(resto, 60)
    # Sem zero à esquerda em nenhum campo: `9°44'0"S`, nunca `09°44'00"S`.
    return f"{graus}°{minutos}'{segundos}\"{hemisferio}"


def _cruzamentos(
    valores: list[float],
    *,
    fixo_min: float,
    fixo_max: float,
    para_proj: Transformer,
    eixo: str,
    limites_proj: tuple[float, float, float, float],
) -> dict[float, tuple[float, float]]:
    """Onde cada meridiano/paralelo corta as duas bordas opostas do quadro.

    Devolve `{valor_graus: (posicao_borda_inicial, posicao_borda_final)}` em
    coordenada projetada. Meridianos não são verticais em UTM — daí amostrar a
    linha inteira e interpolar o cruzamento, em vez de projetar um ponto só.
    """
    x0, y0, x1, y1 = limites_proj
    saida: dict[float, tuple[float, float]] = {}
    amostras = np.linspace(fixo_min, fixo_max, AMOSTRAS)

    for valor in valores:
        if eixo == "x":
            lon = np.full_like(amostras, valor)
            lat = amostras
        else:
            lon = amostras
            lat = np.full_like(amostras, valor)
        px, py = para_proj.transform(lon, lat)

        if eixo == "x":
            # Cruzamento com as bordas inferior (y0) e superior (y1).
            if py[0] > py[-1]:
                py, px = py[::-1], px[::-1]
            if py[0] > y0 or py[-1] < y1:
                continue
            pos_ini = float(np.interp(y0, py, px))
            pos_fim = float(np.interp(y1, py, px))
            if not (x0 <= pos_ini <= x1) and not (x0 <= pos_fim <= x1):
                continue
        else:
            # Cruzamento com as bordas esquerda (x0) e direita (x1).
            if px[0] > px[-1]:
                px, py = px[::-1], py[::-1]
            if px[0] > x0 or px[-1] < x1:
                continue
            pos_ini = float(np.interp(x0, px, py))
            pos_fim = float(np.interp(x1, px, py))
            if not (y0 <= pos_ini <= y1) and not (y0 <= pos_fim <= y1):
                continue

        saida[valor] = (pos_ini, pos_fim)
    return saida


def calcular(
    limites_proj: tuple[float, float, float, float],
    *,
    epsg_projetado: int,
    epsg_geografico: int = 4674,
) -> dict:
    """Ticks DMS das 4 bordas para um quadro de mapa em coordenada projetada.

    Devolve `{"x": [...], "y": [...], "passo_segundos": {...}}`, onde cada item
    traz `valor`, `rotulo` e a posição projetada em cada uma das duas bordas.
    """
    x0, y0, x1, y1 = limites_proj
    para_geo = Transformer.from_crs(f"EPSG:{epsg_projetado}", f"EPSG:{epsg_geografico}", always_xy=True)
    para_proj = Transformer.from_crs(f"EPSG:{epsg_geografico}", f"EPSG:{epsg_projetado}", always_xy=True)

    cantos_x = [x0, x0, x1, x1]
    cantos_y = [y0, y1, y0, y1]
    lons, lats = para_geo.transform(cantos_x, cantos_y)
    lon_min, lon_max = float(min(lons)), float(max(lons))
    lat_min, lat_max = float(min(lats)), float(max(lats))

    passo_x = escolher_passo(lon_max - lon_min)
    passo_y = escolher_passo(lat_max - lat_min)

    # Folga de um passo para fora: o meridiano precisa atravessar o quadro
    # inteiro para o cruzamento com as bordas existir.
    folga_x = passo_x / 3600.0
    folga_y = passo_y / 3600.0

    cruz_x = _cruzamentos(
        valores_ticks(lon_min, lon_max, passo_x),
        fixo_min=lat_min - folga_y,
        fixo_max=lat_max + folga_y,
        para_proj=para_proj,
        eixo="x",
        limites_proj=limites_proj,
    )
    cruz_y = _cruzamentos(
        valores_ticks(lat_min, lat_max, passo_y),
        fixo_min=lon_min - folga_x,
        fixo_max=lon_max + folga_x,
        para_proj=para_proj,
        eixo="y",
        limites_proj=limites_proj,
    )

    eixo_x = [
        {
            "valor": valor,
            "rotulo": formatar(valor, eixo="x"),
            "inferior": pos[0],
            "superior": pos[1],
        }
        for valor, pos in sorted(cruz_x.items())
    ]
    eixo_y = [
        {
            "valor": valor,
            "rotulo": formatar(valor, eixo="y"),
            "esquerda": pos[0],
            "direita": pos[1],
        }
        for valor, pos in sorted(cruz_y.items())
    ]

    return {
        "x": eixo_x,
        "y": eixo_y,
        "passo_segundos": {"x": passo_x, "y": passo_y},
        "limites_geo": {
            "lon_min": lon_min,
            "lon_max": lon_max,
            "lat_min": lat_min,
            "lat_max": lat_max,
        },
    }
