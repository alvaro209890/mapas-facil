"""Blocos de layout do perfil Harmonia desenhados em matplotlib (F1-05).

Cada bloco vive num eixo próprio, posicionado pelo retângulo medido do
[`perfil_pagina`](perfil_pagina.py). Nada aqui inventa posição: se um bloco
precisa se mover, o número muda no perfil, não no desenho.

Ordem da faixa inferior, nos dois perfis: **minimapa → metadados → legenda →
logo**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib import patheffects
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.image import imread
from matplotlib.patches import FancyBboxPatch
from matplotlib.patches import Polygon as PolygonPatch
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

from mapasfacil_nucleo.motores.estilos import obter as obter_estilo
from mapasfacil_nucleo.motores.perfil_pagina import Caixa, PerfilPagina

COR_MOLDURA = "black"
COR_MUNICIPIO_VIZINHO = "#FDF3D7"
COR_MUNICIPIO_ALVO = "#F4A460"
COR_UF = "#C5E0B4"
COR_GUIA = "#FF0000"

# W9-03 — espessuras e halos acompanham a folha.
#
# Até aqui a moldura, a grade, os swatches da legenda e o halo do rótulo eram
# **pt literais**. Numa A0 (841 mm de largura) uma moldura de 1,2 pt fica fina
# como cabelo, porque a folha cresceu ~4× e a linha não. Toda grandeza de
# espessura/fonte passa a ser multiplicada por `k = folha / A4` via
# `PerfilPagina.escalado`, que em A4 (k = 1,0) devolve o próprio valor — o
# gabarito medido não muda em um único bit.
LARGURA_HALO_PT = 2.6
"""Espessura base do halo, em pt, **na A4**. As demais folhas multiplicam por `k`."""


def halos(perfil: PerfilPagina | None = None, claro: bool = False) -> list[Any]:
    """Lista de `path_effects` de contorno, com a espessura escalada pela folha (W9-03).

    Substitui as antigas constantes `HALO_ESCURO`/`HALO_CLARO`, que carregavam os
    2,6 pt congelados — corretos só em A4 e invisíveis no papel grande. `perfil=None`
    devolve o valor de A4 **sem escala** (compatibilidade com chamadas antigas), nunca
    um erro; `claro=True` usa contorno branco, `claro=False` o escuro.
    """
    espessura = perfil.escalado(LARGURA_HALO_PT) if perfil is not None else LARGURA_HALO_PT
    return [patheffects.withStroke(linewidth=espessura, foreground="white" if claro else "#1A1A1A")]


def _eixo(fig: Figure, perfil: PerfilPagina, caixa: Caixa, *, zorder: int = 5) -> Axes:
    ax = fig.add_axes(perfil.fracao(caixa), zorder=zorder)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return ax


def eixo_pagina(fig: Figure) -> Axes:
    """Eixo transparente do tamanho da página, para desenhar entre blocos."""
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], zorder=20)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.patch.set_alpha(0.0)
    return ax


def mm_para_figura(perfil: PerfilPagina, x_mm: float, y_mm: float) -> tuple[float, float]:
    """mm com Y do topo → fração de figura com Y de baixo."""
    return (x_mm / perfil.largura_mm, (perfil.altura_mm - y_mm) / perfil.altura_mm)


def eixo_mm(fig: Figure, perfil: PerfilPagina, *, zorder: int = 25) -> Axes:
    """Eixo do tamanho da página em **mm**, Y crescendo para baixo (igual ao perfil).

    A figura tem a proporção da folha, então 1 mm vale o mesmo nos dois eixos: é aqui que
    se desenha caixa de canto arredondado sem o arredondamento virar elipse.
    """
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], zorder=zorder)
    ax.set_axis_off()
    ax.set_xlim(0, perfil.largura_mm)
    ax.set_ylim(perfil.altura_mm, 0)
    ax.patch.set_alpha(0.0)
    return ax


# --------------------------------------------------------------------------- #
# Fontes medidas dos PDFs-modelo
# --------------------------------------------------------------------------- #

PT_PARA_MM = 25.4 / 72.0

FONTE_TITULO: tuple[str, ...] = ("Tahoma", "Liberation Sans", "Arial", "DejaVu Sans")
"""Os títulos do acervo são **Tahoma Bold** (lido do PDF de cada modelo). O motor
desenhava em DejaVu Serif Bold, ~15% mais larga: "Tipologia Vegetal" passava 11 mm da
caixa medida e "DINÂMICA DE USO DO SOLO - 2008" vazava da caixa no teste_22. Sem
Tahoma (servidor Linux), a Liberation Sans tem as métricas da Arial."""

FONTE_QUADRO: tuple[str, ...] = ("Cambria", "Liberation Serif", "Times New Roman", "DejaVu Serif")
"""Quadro de resumo dos modelos da Aline: **Cambria Bold** 14 pt, branco no cinza-escuro."""

FAMILIAS_ESTILO: dict[str, tuple[str, ...]] = {"sans": FONTE_TITULO, "serif": FONTE_QUADRO}


@lru_cache(maxsize=32)
def familia_disponivel(preferencias: tuple[str, ...], negrito: bool = False) -> str:
    """Primeira família da lista que existe nesta máquina (sem o aviso do matplotlib).

    Só vale fonte em arquivo `.ttf`/`.otf` no peso pedido: a Cambria normal do Windows vem
    em `.ttc` (coleção com a Cambria Math), e o Agg desenha **nada** com ela — a grade do
    PNG saía sem rótulo nenhum, enquanto o PDF saía certo.
    """
    from matplotlib import font_manager

    peso = 700 if negrito else 400
    for nome in preferencias:
        arquivos = [
            f.fname
            for f in font_manager.fontManager.ttflist
            if f.name == nome
            and f.style == "normal"
            and (int(f.weight) >= 600) == (peso >= 600)
        ]
        if any(not a.lower().endswith(".ttc") for a in arquivos):
            return nome
    return "DejaVu Sans"


@lru_cache(maxsize=1024)
def _largura_linha_mm(texto: str, pt: float, familia: str, negrito: bool) -> float:
    if not texto.strip():
        return 0.0
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    props = FontProperties(family=familia, size=pt, weight="bold" if negrito else "normal")
    return float(TextPath((0, 0), texto, prop=props).get_extents().width) * PT_PARA_MM


ENTRELINHA_BLOCO = 1.18
"""Altura de linha dos blocos de texto de várias linhas (título quebrado, quadro)."""


def medir_bloco_mm(texto: str, pt: float, familia: str, *, negrito: bool = True) -> tuple[float, float]:
    """(largura, altura) em mm de um texto de uma ou mais linhas, pela fonte real."""
    linhas = texto.split("\n") or [""]
    largura = max(_largura_linha_mm(linha, pt, familia, negrito) for linha in linhas)
    altura = len(linhas) * pt * PT_PARA_MM * ENTRELINHA_BLOCO
    return largura, altura


def _duas_linhas(texto: str) -> str:
    """Quebra em duas linhas o mais equilibradas possível (por palavra)."""
    palavras = texto.split()
    if len(palavras) < 2:
        return texto
    melhor, menor_diff = texto, float("inf")
    for i in range(1, len(palavras)):
        a, b = " ".join(palavras[:i]), " ".join(palavras[i:])
        diff = abs(len(a) - len(b))
        if diff < menor_diff:
            melhor, menor_diff = f"{a}\n{b}", diff
    return melhor


@dataclass(frozen=True)
class PlanoTexto:
    """Onde e como um bloco de texto com moldura vai ser desenhado (mm, Y para baixo)."""

    caixa: Caixa
    texto: str
    pt: float
    familia: str
    forma: str = "reta"
    fundo: str = "white"
    borda: str = "black"
    cor_texto: str = "black"


def planejar_titulo(perfil: PerfilPagina, texto: str, estilo: dict[str, Any] | None = None) -> PlanoTexto:
    """Caixa de título que **sempre** contém o texto.

    1. mede o texto com a fonte que vai ser usada (não com uma estimativa);
    2. se não cabe na caixa medida do modelo, a caixa cresce para os lados, centrada, até
       encostar na margem do quadro ou na rosa dos ventos;
    3. se ainda não cabe, o corpo desce até 70%; por fim o texto quebra em duas linhas e
       a caixa cresce para baixo.

    `estilo` (de `ajustes_layout.titulo`): `fonte` (`sans`/`serif`), `forma`
    (`reta`/`arredondada`), `caixa_justa` (moldura colada no texto, como nos modelos da
    Aline) e `escala` (multiplica o corpo).
    """
    estilo = estilo or {}
    familia = familia_disponivel(FAMILIAS_ESTILO.get(str(estilo.get("fonte") or "sans"), FONTE_TITULO), True)
    forma = "arredondada" if estilo.get("forma") == "arredondada" else "reta"
    justa = bool(estilo.get("caixa_justa"))
    pt = perfil.pt_titulo * float(estilo.get("escala") or 1.0)
    base = perfil.titulo
    cx = base.centro[0]
    folga_x = perfil.escalado(3.0)
    folga_y = perfil.escalado(1.4)

    esquerda = perfil.mapa.x0 + perfil.escalado(3.0)
    direita = perfil.mapa.x1 - perfil.escalado(3.0)
    if perfil.rosa.x0 > cx:
        direita = min(direita, perfil.rosa.x0 - perfil.escalado(2.0))
    largura_max = max(2.0 * min(cx - esquerda, direita - cx), base.largura)

    texto_final = " ".join(str(texto or "").split())
    piso = pt * 0.7
    largura, altura = medir_bloco_mm(texto_final, pt, familia)
    while largura + 2 * folga_x > largura_max and pt > piso:
        pt *= 0.94
        largura, altura = medir_bloco_mm(texto_final, pt, familia)
    if largura + 2 * folga_x > largura_max:
        texto_final = _duas_linhas(texto_final)
        largura, altura = medir_bloco_mm(texto_final, pt, familia)
        while largura + 2 * folga_x > largura_max and pt > piso * 0.8:
            pt *= 0.94
            largura, altura = medir_bloco_mm(texto_final, pt, familia)

    w = largura + 2 * folga_x
    h = altura + 2 * folga_y
    if not justa:
        w = max(w, base.largura)
        h = max(h, base.altura)
    caixa = Caixa(cx - w / 2.0, base.y0, cx + w / 2.0, base.y0 + h)
    return PlanoTexto(caixa=caixa, texto=texto_final, pt=pt, familia=familia, forma=forma)


def _desenhar_plano(fig: Figure, perfil: PerfilPagina, plano: PlanoTexto, *, zorder: int = 25) -> None:
    ax = eixo_mm(fig, perfil, zorder=zorder)
    c = plano.caixa
    if plano.forma == "arredondada":
        raio = min(c.altura, c.largura) * 0.16
        moldura = FancyBboxPatch(
            (c.x0, c.y0),
            c.largura,
            c.altura,
            boxstyle=f"round,pad=0,rounding_size={raio}",
            facecolor=plano.fundo,
            edgecolor=plano.borda,
            linewidth=perfil.escalado(1.2),
        )
    else:
        moldura = Rectangle(
            (c.x0, c.y0),
            c.largura,
            c.altura,
            facecolor=plano.fundo,
            edgecolor=plano.borda,
            linewidth=perfil.escalado(1.0),
        )
    ax.add_patch(moldura)
    ax.text(
        c.centro[0],
        c.centro[1],
        plano.texto,
        ha="center",
        va="center",
        multialignment="center",
        fontsize=plano.pt,
        fontweight="bold",
        family=plano.familia,
        color=plano.cor_texto,
        linespacing=ENTRELINHA_BLOCO,
    )


def planejar_quadro_resumo(
    perfil: PerfilPagina, linhas: list[str], estilo: dict[str, Any] | None = None
) -> PlanoTexto | None:
    """Quadro escuro no canto inferior-direito do mapa (modelo "Dinâmica 2008" da Aline).

    Texto centrado, Cambria Bold 14 pt branco sobre `#333333`, cantos arredondados, a
    ~1 mm da moldura. Encolhe o corpo se o texto passar de 60% da largura do quadro.
    """
    estilo = estilo or {}
    texto = "\n".join(str(linha) for linha in linhas if str(linha).strip())
    if not texto:
        return None
    familia = familia_disponivel(FAMILIAS_ESTILO.get(str(estilo.get("fonte") or "serif"), FONTE_QUADRO), True)
    pt = perfil.escalado(float(estilo.get("pt") or 14.0))
    folga_x, folga_y = perfil.escalado(2.4), perfil.escalado(1.6)
    limite = perfil.mapa.largura * 0.6
    largura, altura = medir_bloco_mm(texto, pt, familia)
    while largura + 2 * folga_x > limite and pt > perfil.escalado(8.0):
        pt *= 0.94
        largura, altura = medir_bloco_mm(texto, pt, familia)
    margem = perfil.escalado(1.2)
    x1 = perfil.mapa.x1 - margem
    y1 = perfil.mapa.y1 - margem
    caixa = Caixa(x1 - largura - 2 * folga_x, y1 - altura - 2 * folga_y, x1, y1)
    return PlanoTexto(
        caixa=caixa,
        texto=texto,
        pt=pt,
        familia=familia,
        forma="arredondada",
        fundo=str(estilo.get("fundo") or "#333333"),
        borda=str(estilo.get("borda") or "white"),
        cor_texto=str(estilo.get("cor_texto") or "white"),
    )


def quadro_resumo(fig: Figure, perfil: PerfilPagina, plano: PlanoTexto) -> Caixa:
    """Desenha o quadro planejado e devolve a caixa que ele ocupa."""
    _desenhar_plano(fig, perfil, plano, zorder=27)
    return plano.caixa


# --------------------------------------------------------------------------- #
# Título e rosa dos ventos
# --------------------------------------------------------------------------- #


def caixa_titulo(
    fig: Figure,
    perfil: PerfilPagina,
    texto: str,
    *,
    estilo: dict[str, Any] | None = None,
    plano: PlanoTexto | None = None,
) -> Caixa:
    """Caixa branca com borda preta e o título em Tahoma Bold — topo-centro.

    Devolve a caixa desenhada (maior que a medida do modelo quando o título é longo): o
    enquadramento usa essa caixa para não deixar o imóvel embaixo dela.
    """
    plano = plano or planejar_titulo(perfil, texto, estilo)
    _desenhar_plano(fig, perfil, plano, zorder=25)
    return plano.caixa


def rosa_dos_ventos(fig: Figure, perfil: PerfilPagina) -> None:
    """Rosa dos ventos com N/S/E/W — **não** é a seta triangular simples."""
    ax = _eixo(fig, perfil, perfil.rosa, zorder=25)
    cx, cy, raio = 0.5, 0.5, 0.34

    # Pontas cardeais (compridas) e colaterais (curtas), cada uma com metade
    # clara e metade escura, como na rosa da fonte ESRI North.
    for i in range(8):
        ang = math.radians(90 - i * 45)
        comprimento = raio if i % 2 == 0 else raio * 0.55
        largura = 0.10 if i % 2 == 0 else 0.07
        px, py = cx + comprimento * math.cos(ang), cy + comprimento * math.sin(ang)
        ang_perp = ang + math.pi / 2
        bx, by = cx + largura * math.cos(ang_perp), cy + largura * math.sin(ang_perp)
        cx2, cy2 = cx - largura * math.cos(ang_perp), cy - largura * math.sin(ang_perp)
        ax.add_patch(
            PolygonPatch(
                [(cx, cy), (bx, by), (px, py)],
                closed=True,
                facecolor="white",
                edgecolor="black",
                linewidth=perfil.escalado(0.5),
            )
        )
        ax.add_patch(
            PolygonPatch(
                [(cx, cy), (cx2, cy2), (px, py)],
                closed=True,
                facecolor="#333333",
                edgecolor="black",
                linewidth=perfil.escalado(0.5),
            )
        )

    for letra, (dx, dy) in {
        "N": (0.0, 0.46),
        "S": (0.0, -0.46),
        "E": (0.42, 0.0),
        "W": (-0.42, 0.0),
    }.items():
        ax.text(
            cx + dx,
            cy + dy,
            letra,
            ha="center",
            va="center",
            fontsize=perfil.escalado(5.5),
            fontweight="bold",
            color="black",
        )


# --------------------------------------------------------------------------- #
# Moldura e grade DMS do quadro do mapa
# --------------------------------------------------------------------------- #


def moldura_e_grade(
    ax: Axes,
    perfil: PerfilPagina,
    grade: dict[str, Any],
    *,
    com_linhas: bool = False,
) -> None:
    """Moldura preta + ticks e rótulos DMS nas 4 bordas (sem linhas internas)."""
    for lado in ("left", "right", "top", "bottom"):
        ax.spines[lado].set_visible(True)
        ax.spines[lado].set_linewidth(perfil.escalado(1.2))
        ax.spines[lado].set_color(COR_MOLDURA)
    ax.set_xticks([])
    ax.set_yticks([])

    # Tick e afastamento do rótulo em **mm de papel**. Eram 0,8% do eixo: no retrato o
    # rótulo de cima ficava a 3,2 mm da moldura, que começa a 5 mm da borda — e o texto
    # saía da folha cortado (teste_22: coordenadas do topo sem as aspas dos segundos).
    tick_mm = perfil.escalado(1.1)
    vao_mm = perfil.escalado(0.5)
    altura_rotulo_mm = perfil.pt_grade * PT_PARA_MM * 1.05
    familia_grade = familia_disponivel(perfil.fonte_grade) if perfil.fonte_grade else None
    espaco_topo = max(perfil.mapa.y0 - perfil.escalado(0.4), 0.0)
    if tick_mm + vao_mm + altura_rotulo_mm > espaco_topo:
        # Pouco papel acima da moldura: encurta o tick antes de o texto sair da folha.
        tick_mm = max(espaco_topo - vao_mm - altura_rotulo_mm, perfil.escalado(0.4))
    altura_eixo_mm = max(perfil.mapa.altura, 1e-6)
    largura_eixo_mm = max(perfil.mapa.largura, 1e-6)
    trans_x = blended_transform_factory(ax.transData, ax.transAxes)
    trans_y = blended_transform_factory(ax.transAxes, ax.transData)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()

    for item in grade.get("x", []):
        for chave, base, sentido, va in (
            ("inferior", 0.0, -1.0, "top"),
            ("superior", 1.0, 1.0, "bottom"),
        ):
            pos = item[chave]
            if not (x0 <= pos <= x1):
                continue
            tam_tick = tick_mm / altura_eixo_mm
            ax.plot(
                [pos, pos],
                [base, base + sentido * tam_tick],
                transform=trans_x,
                color=COR_MOLDURA,
                linewidth=perfil.escalado(0.8),
                clip_on=False,
                zorder=30,
            )
            ax.text(
                pos,
                base + sentido * (tick_mm + vao_mm) / altura_eixo_mm,
                item["rotulo"],
                transform=trans_x,
                ha="center",
                va=va,
                fontsize=perfil.pt_grade,
                family=familia_grade,
                color="black",
                clip_on=False,
                zorder=30,
            )
        if com_linhas:
            ax.plot(
                [item["inferior"], item["superior"]],
                [y0, y1],
                color="#999999",
                linewidth=perfil.escalado(0.4),
                zorder=6,
            )

    for item in grade.get("y", []):
        # Os dois lados escrevem de baixo para cima (90°), como no ArcMap. Girado 90°, o
        # "pé" do texto aponta para a direita: à esquerda o texto se apoia pelo pé
        # (`va=bottom`), à direita pela cabeça (`va=top`), e fica **fora** da moldura.
        # Antes era `va=center` — metade do rótulo da direita caía em cima do mapa.
        for chave, base, sentido, va in (
            ("esquerda", 0.0, -1.0, "bottom"),
            ("direita", 1.0, 1.0, "top"),
        ):
            pos = item[chave]
            if not (y0 <= pos <= y1):
                continue
            tam_tick = tick_mm / largura_eixo_mm
            ax.plot(
                [base, base + sentido * tam_tick],
                [pos, pos],
                transform=trans_y,
                color=COR_MOLDURA,
                linewidth=perfil.escalado(0.8),
                clip_on=False,
                zorder=30,
            )
            ax.text(
                base + sentido * (tick_mm + vao_mm) / largura_eixo_mm,
                pos,
                item["rotulo"],
                transform=trans_y,
                ha="center",
                va=va,
                rotation=90,
                rotation_mode="anchor",
                fontsize=perfil.pt_grade,
                family=familia_grade,
                color="black",
                clip_on=False,
                zorder=30,
            )
        if com_linhas:
            ax.plot(
                [x0, x1],
                [item["esquerda"], item["direita"]],
                color="#999999",
                linewidth=perfil.escalado(0.4),
                zorder=6,
            )


def rotulo_imovel(
    ax: Axes,
    ponto: tuple[float, float],
    texto: str,
    *,
    pt: float = 9.0,
    perfil: PerfilPagina | None = None,
) -> None:
    """Nome do imóvel no centroide, branco com halo escuro, acima das hachuras.

    W9-03: com `perfil`, a fonte e o halo do rótulo crescem com a folha (`pt` é o
    tamanho de A4). Sem `perfil`, mantém o valor histórico de A4 — nenhuma chamada
    antiga muda de resultado.
    """
    ax.text(
        ponto[0],
        ponto[1],
        texto,
        ha="center",
        va="center",
        fontsize=perfil.escalado(pt) if perfil is not None else pt,
        color="white",
        fontweight="bold",
        path_effects=halos(perfil, claro=False),
        zorder=15,
    )


# --------------------------------------------------------------------------- #
# Faixa inferior
# --------------------------------------------------------------------------- #


ENTRELINHA = 1.15
"""Espaçamento medido nos blocos de texto do acervo."""


def _passo_linha(pt: float, altura_caixa_mm: float) -> float:
    """Altura de uma linha em fração da caixa (1 pt = 0,3528 mm)."""
    return (pt * 0.3528 * ENTRELINHA) / max(altura_caixa_mm, 1e-6)


def pt_metadados_efetivo(perfil: PerfilPagina, n_linhas: int, *, piso: float = 0.6) -> float:
    """Corpo do bloco de METADADOS pelo número de linhas (W9-12 / W-17 §5).

    A lição da skill é "16 pt que desce para 14 com 6 linhas e 12 com 5" — na prática, a regra
    que importa é **o bloco não estourar a caixa**. Aqui o corte é derivado da geometria real
    do perfil: reduz de 10% em 10% até caber, com piso para o texto não virar letra miúda.
    Com 4–6 linhas nada muda (o perfil medido já cabe), então o golden da A4 fica igual.
    """
    base = perfil.pt_metadados
    limite = 0.98 * perfil.metadados.altura
    pt = base
    while pt > base * piso:
        passo = _passo_linha(pt, perfil.metadados.altura) * perfil.metadados.altura
        if passo * (n_linhas + 0.6) <= limite:
            break
        pt *= 0.9
    return max(pt, base * piso)


def bloco_metadados(
    fig: Figure,
    perfil: PerfilPagina,
    pares: list[dict[str, Any]],
    *,
    titulo: str = "METADADOS IMAGEM",
) -> int:
    """Lista de pares rótulo/valor, rótulo em negrito, centralizada.

    Devolve quantas linhas foram desenhadas — o validador usa isso para o check
    de bloco vazio.
    """
    ax = _eixo(fig, perfil, perfil.metadados, zorder=25)
    linhas = [p for p in pares if str(p.get("valor") or "").strip()]
    # W9-12: 7 linhas ou mais não cabem no corpo medido — encolhe até caber.
    pt_corpo = pt_metadados_efetivo(perfil, len(linhas))
    passo = _passo_linha(pt_corpo, perfil.metadados.altura)
    # Ancorado na **base** da caixa, como no modelo: um bloco com menos linhas
    # sobe a partir do rodapé, em vez de esticar para preencher a caixa.
    y = passo * (len(linhas) + 0.6)

    ax.text(
        0.5,
        y,
        titulo,
        ha="center",
        va="center",
        fontsize=pt_corpo + perfil.escalado(1.0),
        fontweight="bold",
        color="black",
    )
    y -= passo

    largura_caixa_mm = max(perfil.metadados.largura, 1.0)
    for par in linhas:
        rotulo = str(par.get("rotulo") or "").strip()
        valor = str(par.get("valor") or "").strip()
        # O modelo centraliza a **linha inteira**, não os dois-pontos. Ancorar no
        # meio da caixa deslocava o bloco em 19 mm quando rótulo e valor têm
        # comprimentos muito diferentes ("Fonte: WMS FUNAI" × "Datum: SIRGAS
        # 2000 UTM 22 S"), e a âncora do bloco saía fora da tolerância.
        largura_rotulo = largura_texto_mm(f"{rotulo}: ", perfil.pt_metadados, negrito=True)
        largura_valor = largura_texto_mm(f" {valor}", perfil.pt_metadados)
        ancora = 0.5 + (largura_rotulo - largura_valor) / 2.0 / largura_caixa_mm
        ax.text(
            ancora,
            y,
            f"{rotulo}: ",
            ha="right",
            va="center",
            fontsize=perfil.pt_metadados,
            fontweight="bold",
            color="black",
        )
        ax.text(
            ancora,
            y,
            f" {valor}",
            ha="left",
            va="center",
            fontsize=perfil.pt_metadados,
            color="black",
        )
        y -= passo

    return len(linhas)


@lru_cache(maxsize=512)
def largura_texto_mm(texto: str, pt: float, *, negrito: bool = False) -> float:
    """Largura real do texto em mm, pela fonte que o motor vai usar de fato.

    Estimar por "largura média de caractere" erra o suficiente para deslocar um
    bloco centralizado: a mesma estimativa que centrava bem o bloco de Terras
    Indígenas jogava o das Dinâmicas 8 mm para o lado. `TextPath` mede sem
    rasterizar nada.
    """
    if not texto:
        return 0.0
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    props = FontProperties(size=pt, weight="bold" if negrito else "normal")
    caminho = TextPath((0, 0), texto, prop=props)
    largura_pt = caminho.get_extents().width
    return float(largura_pt) * 25.4 / 72.0


LARGURA_CHAR_MM_POR_PT = 0.175
"""Largura média de caractere da Liberation Sans/Arial: ~0,50 em × 0,3528 mm/pt.

Era 0,2 (DejaVu Sans, mais larga). Mudou junto com a fonte do motor — ver
`nativo.FAMILIA_FONTE`: com o valor antigo o texto "cabia" com folga demais e a
legenda quebrava linhas que o modelo não quebra."""


def _quebrar(texto: str, largura_mm: float, pt: float) -> str:
    """Quebra o rótulo para caber na largura da caixa, em linhas de palavras.

    Mede o texto de verdade (`largura_texto_mm`) antes de decidir: a estimativa
    por caractere quebrava "Tipologia: Floresta" em duas linhas num espaço onde
    ele cabe inteiro no modelo.

    W9-03: **nada aqui mudou** — e não deve mudar. `largura_mm` chega da caixa já
    multiplicada por `k` (`perfil.titulo.largura`, `perfil.legenda.largura`) e `pt`
    chega dos `pt_*` já multiplicados por `k`. Como texto medido e caixa crescem na
    mesma proporção, a razão é folha-invariante: um rótulo quebra nas **mesmas**
    linhas em A4 e em A0. Por isso o piso de 8 caracteres fica **fixo** — escalá-lo
    faria a caixa pequena quebrar diferente em folha grande, quebrando justamente a
    invariância que a folha proporcional promete.
    """
    if largura_texto_mm(texto, pt) <= largura_mm:
        return texto
    max_chars = max(int(largura_mm / (pt * LARGURA_CHAR_MM_POR_PT)) or 1, 8)
    if len(texto) <= max_chars:
        return texto
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split():
        candidato = f"{atual} {palavra}".strip()
        if len(candidato) <= max_chars or not atual:
            atual = candidato
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return "\n".join(linhas)


def bloco_legenda(fig: Figure, perfil: PerfilPagina, itens: list[dict[str, Any]]) -> int:
    """Swatch de polígono + rótulo. Vazado para o imóvel, sólido para temáticas."""
    ax = _eixo(fig, perfil, perfil.legenda, zorder=25)
    if not itens:
        return 0

    # Amostra de tamanho **fixo em papel** (≈6,5 × 3,2 mm em A4), com o texto logo ao lado —
    # medida nas legendas da Dinâmica 2026 e da Dinâmica 2008 da Aline. Era 20% da caixa
    # mais 6% de vão: sobrava pouco para o texto e "Área de vegetação nativa" quebrava.
    largura_caixa_mm = max(perfil.legenda.largura, 1e-6)
    altura_caixa_mm = max(perfil.legenda.altura, 1e-6)
    largura_swatch_mm = perfil.escalado(6.5)
    vao_mm = perfil.escalado(1.7)
    largura_swatch = largura_swatch_mm / largura_caixa_mm
    largura_texto_mm = largura_caixa_mm - largura_swatch_mm - vao_mm

    # O espaço da caixa é contado em **linhas de texto**, não em itens: um
    # rótulo que quebra em três linhas ocupa três, e é isso que evita a legenda
    # sobrepor a si mesma quando os nomes são longos.
    pt = perfil.pt_legenda
    for _tentativa in range(5):
        rotulos = [_quebrar(str(i.get("rotulo") or ""), largura_texto_mm, pt) for i in itens]
        linhas_por_item = [r.count("\n") + 1 for r in rotulos]
        total_linhas = sum(linhas_por_item) + 1  # +1 do título
        passo_linha = _passo_linha(pt, perfil.legenda.altura)
        if total_linhas * passo_linha <= 1.0 or pt <= perfil.pt_legenda * 0.55:
            break
        pt *= 0.85
    # Cada linha ocupa ao menos a amostra e um respiro (≈4,7 mm em A4, medido nos modelos),
    # quando cabe: o passo só pelo corpo da letra espremia os itens com a fonte de 7 pt.
    passo_amostra = perfil.escalado(4.7) / altura_caixa_mm
    if total_linhas * passo_amostra <= 1.0:
        passo_linha = max(passo_linha, passo_amostra)

    # Ancorada na base da caixa, como o bloco de metadados.
    y = passo_linha * (total_linhas - 0.3)

    ax.text(
        0.0,
        y,
        perfil.titulo_legenda,
        ha="left",
        va="center",
        fontsize=getattr(perfil, "pt_legenda_titulo", 0.0) or (pt + perfil.escalado(1.0)),
        fontweight="bold",
        color="black",
    )
    y -= passo_linha

    for item, rotulo, n_linhas in zip(itens, rotulos, linhas_por_item):
        estilo = obter_estilo(item.get("estilo"))
        # Limite municipal e estadual são **linha** no mapa e **quadrado
        # preenchido** na legenda — é assim nos modelos, e pintar o polígono no
        # mapa cobria a imagem de satélite inteira com laranja.
        face = estilo.get("cor_preenchimento_legenda", estilo.get("cor_preenchimento"))
        centro = y - passo_linha * (n_linhas - 1) / 2.0
        altura_swatch = min(passo_linha * 0.72, perfil.escalado(3.2) / altura_caixa_mm)
        # Contorno com a espessura do traço no mapa (o imóvel grosso, o limite estadual
        # fino), como o ArcMap desenha a amostra; cantos arredondados como nos modelos.
        largura_traco = min(max(float(estilo.get("largura") or 1.0), 0.6), 2.6)
        raio = largura_swatch * 0.12
        amostra = FancyBboxPatch(
            (0.0, centro - altura_swatch / 2),
            largura_swatch,
            altura_swatch,
            boxstyle=f"round,pad=0,rounding_size={raio}",
            mutation_aspect=largura_caixa_mm / altura_caixa_mm,
            transform=ax.transAxes,
            facecolor=face if face else "none",
            edgecolor=estilo["cor_linha"],
            linewidth=perfil.escalado(largura_traco),
            # A hachura da camada também na amostra, como na legenda do ArcMap.
            hatch=estilo.get("hachura_legenda", estilo.get("hachura")),
        )
        if estilo.get("largura_hachura") and hasattr(amostra, "set_hatch_linewidth"):
            amostra.set_hatch_linewidth(perfil.escalado(float(estilo["largura_hachura"])))
        ax.add_patch(amostra)
        ax.text(
            largura_swatch + vao_mm / largura_caixa_mm,
            centro,
            rotulo,
            ha="left",
            va="center",
            fontsize=pt,
            color="black",
            linespacing=1.05,
        )
        y -= passo_linha * n_linhas

    return len(itens)


def _recortar_conteudo(img: np.ndarray) -> np.ndarray:
    """Corta a moldura transparente do PNG.

    O logo do acervo é uma tela de 8334×8334 com **2%** de pixels opacos: sem
    este corte a marca sai minúscula e apagada dentro da caixa.
    """
    if img.ndim != 3 or img.shape[2] < 4:
        return img
    opaco = img[:, :, 3] > (0.04 if img.dtype.kind == "f" else 10)
    if not opaco.any():
        return img
    linhas = np.where(opaco.any(axis=1))[0]
    colunas = np.where(opaco.any(axis=0))[0]
    return img[linhas[0] : linhas[-1] + 1, colunas[0] : colunas[-1] + 1]


def bloco_logo(fig: Figure, perfil: PerfilPagina, caminho: Path | None) -> bool:
    """Marca IMAP no canto inferior-direito. Ausente → bloco vazio, sem erro."""
    if caminho is None or not Path(caminho).is_file():
        return False
    try:
        img = _recortar_conteudo(imread(str(caminho)))
    except Exception:  # noqa: BLE001 — logo ilegível não derruba o mapa
        return False

    # Encaixa a marca na caixa preservando a proporção (nunca esticar a marca).
    caixa = perfil.logo
    razao_img = img.shape[0] / max(img.shape[1], 1)
    largura_mm = caixa.largura
    altura_mm = largura_mm * razao_img
    if altura_mm > caixa.altura:
        altura_mm = caixa.altura
        largura_mm = altura_mm / razao_img
    cx, cy = caixa.centro
    encaixe = Caixa(
        cx - largura_mm / 2,
        cy - altura_mm / 2,
        cx + largura_mm / 2,
        cy + altura_mm / 2,
    )

    ax = _eixo(fig, perfil, encaixe, zorder=25)
    ax.imshow(img, extent=(0, 1, 0, 1), aspect="auto", interpolation="bilinear")
    return True


def _dentro_da_folha(perfil: PerfilPagina, caixa: Caixa) -> Caixa:
    """Afasta da borda do papel uma caixa que encosta nela (a moldura não sai cortada)."""
    margem = perfil.escalado(2.0)
    return Caixa(
        max(caixa.x0, margem),
        max(caixa.y0, margem),
        min(caixa.x1, perfil.largura_mm - margem),
        min(caixa.y1, perfil.altura_mm - margem),
    )


def _geometrias_municipios(
    caminho_shp: Path,
    *,
    uf: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[tuple[str, Any]]:
    """`[(nome, shape)]` filtrado por UF e/ou bbox — sem carregar o Brasil todo."""
    import shapefile

    reader = shapefile.Reader(str(caminho_shp))
    campos = [f[0] for f in reader.fields[1:]]
    i_nome = campos.index("nome") if "nome" in campos else 0
    i_uf = campos.index("sigla_uf") if "sigla_uf" in campos else None

    saida: list[tuple[str, Any]] = []
    for sr in reader.iterShapeRecords():
        if uf and i_uf is not None and str(sr.record[i_uf]).upper() != uf.upper():
            continue
        if bbox is not None:
            bx0, by0, bx1, by1 = sr.shape.bbox
            if bx1 < bbox[0] or bx0 > bbox[2] or by1 < bbox[1] or by0 > bbox[3]:
                continue
        saida.append((str(sr.record[i_nome]), sr.shape))
    return saida


def _desenhar_shape(ax: Axes, shape: Any, **kwargs: Any) -> None:
    pontos = np.asarray(shape.points)
    partes = list(shape.parts) + [len(pontos)]
    for i in range(len(partes) - 1):
        trecho = pontos[partes[i] : partes[i + 1]]
        if len(trecho) < 3:
            continue
        ax.add_patch(PolygonPatch(trecho, closed=True, **kwargs))


def bloco_minimapa(
    fig: Figure,
    perfil: PerfilPagina,
    *,
    municipio: str | None,
    uf: str | None,
    centroide_lonlat: tuple[float, float] | None,
    shp_municipios: Path,
    shp_ufs: Path | None = None,
) -> dict[str, Any]:
    """Inset de município: vizinhos em bege, o do imóvel em laranja, retângulo
    vermelho no imóvel, linha-guia em L até o quadro do mapa e selo da UF.

    A armadilha registrada do trabalho manual (retângulo ~0,4 cm fora do
    centroide em 19 de 19 mapas) não se repete aqui porque a posição é
    **calculada** a partir do centroide, não posicionada à mão.
    """
    info: dict[str, Any] = {"municipio_encontrado": False, "retangulo_ok": False}
    caixa = _dentro_da_folha(perfil, perfil.minimapa)
    ax = fig.add_axes(perfil.fracao(caixa), zorder=25)
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ("left", "right", "top", "bottom"):
        ax.spines[lado].set_visible(True)
        ax.spines[lado].set_linewidth(perfil.escalado(1.0))
        ax.spines[lado].set_color(COR_MOLDURA)
    ax.set_facecolor("white")

    if not shp_municipios.is_file():
        ax.set_axis_off()
        return info

    alvo = (municipio or "").strip().casefold()
    municipios_uf = _geometrias_municipios(shp_municipios, uf=uf)
    alvo_shape = next((s for n, s in municipios_uf if n.casefold() == alvo), None)
    if alvo_shape is None and centroide_lonlat:
        # Sem nome casando, cai no município que contém o centroide.
        lon, lat = centroide_lonlat
        for _n, s in municipios_uf:
            bx0, by0, bx1, by1 = s.bbox
            if bx0 <= lon <= bx1 and by0 <= lat <= by1:
                alvo_shape = s
                break

    if alvo_shape is None:
        ax.set_axis_off()
        return info

    info["municipio_encontrado"] = True
    bx0, by0, bx1, by1 = alvo_shape.bbox
    folga_x = (bx1 - bx0) * 0.45 or 0.2
    folga_y = (by1 - by0) * 0.45 or 0.2
    vista = (bx0 - folga_x, by0 - folga_y, bx1 + folga_x, by1 + folga_y)

    for _nome, shape in _geometrias_municipios(shp_municipios, bbox=vista):
        _desenhar_shape(
            ax,
            shape,
            facecolor=COR_MUNICIPIO_VIZINHO,
            edgecolor="black",
            linewidth=perfil.escalado(0.25),
        )
    _desenhar_shape(
        ax, alvo_shape, facecolor=COR_MUNICIPIO_ALVO, edgecolor="black", linewidth=perfil.escalado(0.5)
    )

    ax.set_xlim(vista[0], vista[2])
    ax.set_ylim(vista[1], vista[3])
    # `datalim`: a moldura fica do tamanho da caixa e a vista cresce para caber. Com `box`
    # o eixo encolhia para a proporção do município (Querência é alto e fino) e o selo da
    # UF, posicionado pela caixa, ficava fora da moldura (teste_22).
    ax.set_aspect("equal", adjustable="datalim")
    ax.apply_aspect()

    if municipio:
        ax.text(
            (bx0 + bx1) / 2,
            (by0 + by1) / 2,
            municipio,
            ha="center",
            va="center",
            fontsize=perfil.escalado(6.5),
            fontweight="bold",
            color="black",
            path_effects=halos(perfil, claro=True),
            zorder=12,
        )

    if centroide_lonlat:
        lon, lat = centroide_lonlat
        lado_x = (vista[2] - vista[0]) * 0.055
        lado_y = (vista[3] - vista[1]) * 0.055
        ax.add_patch(
            Rectangle(
                (lon - lado_x / 2, lat - lado_y / 2),
                lado_x,
                lado_y,
                facecolor="none",
                edgecolor=COR_GUIA,
                linewidth=perfil.escalado(1.4),
                zorder=14,
            )
        )
        info["retangulo_ok"] = True
        info["retangulo_lonlat"] = [lon, lat]

        # Linha-guia em L, desenhada na página (sai do inset e sobe até o quadro). O
        # `apply_aspect` acima já fixou os limites: o ponto de saída é o do retângulo.
        px_dado = ax.transData.transform((lon + lado_x / 2, lat + lado_y / 2))
        px_fig = fig.transFigure.inverted().transform(px_dado)
        alvo_x, alvo_y = mm_para_figura(perfil, perfil.mapa.x0 + perfil.escalado(1.5), perfil.mapa.y1)
        ax_pagina = eixo_pagina(fig)
        ax_pagina.plot(
            [px_fig[0], px_fig[0], alvo_x],
            [px_fig[1], alvo_y, alvo_y],
            color=COR_GUIA,
            linewidth=perfil.escalado(0.9),
            zorder=21,
        )
        info["guia_ok"] = True

    # Selo da UF no canto inferior-esquerdo do inset.
    if shp_ufs and Path(shp_ufs).is_file() and uf:
        largura_selo = 0.34
        altura_selo = 0.42
        frac = perfil.fracao(caixa)
        selo = fig.add_axes(
            [
                frac[0] + frac[2] * 0.02,
                frac[1] + frac[3] * 0.03,
                frac[2] * largura_selo,
                frac[3] * altura_selo,
            ],
            zorder=26,
        )
        selo.set_xticks([])
        selo.set_yticks([])
        for lado in ("left", "right", "top", "bottom"):
            selo.spines[lado].set_linewidth(perfil.escalado(0.8))
            selo.spines[lado].set_color(COR_MOLDURA)
        selo.set_facecolor("white")
        import shapefile as _shp

        reader = _shp.Reader(str(shp_ufs))
        campos = [f[0] for f in reader.fields[1:]]
        i_sigla = campos.index("sigla_uf") if "sigla_uf" in campos else 0
        for sr in reader.iterShapeRecords():
            if str(sr.record[i_sigla]).upper() != uf.upper():
                continue
            _desenhar_shape(selo, sr.shape, facecolor=COR_UF, edgecolor="black", linewidth=perfil.escalado(0.4))
            ux0, uy0, ux1, uy1 = sr.shape.bbox
            selo.set_xlim(ux0, ux1)
            selo.set_ylim(uy0, uy1)
            selo.set_aspect("equal", adjustable="box")
            _desenhar_shape(
                selo, alvo_shape, facecolor=COR_MUNICIPIO_ALVO, edgecolor="black", linewidth=perfil.escalado(0.4)
            )
            selo.text(
                0.5,
                0.12,
                uf.upper(),
                transform=selo.transAxes,
                ha="center",
                va="center",
                fontsize=perfil.escalado(6.0),
                fontweight="bold",
                path_effects=halos(perfil, claro=True),
            )
            info["selo_uf_ok"] = True
            break

    return info
