"""Blocos de layout do perfil Harmonia desenhados em matplotlib (F1-05).

Cada bloco vive num eixo próprio, posicionado pelo retângulo medido do
[`perfil_pagina`](perfil_pagina.py). Nada aqui inventa posição: se um bloco
precisa se mover, o número muda no perfil, não no desenho.

Ordem da faixa inferior, nos dois perfis: **minimapa → metadados → legenda →
logo**.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib import patheffects
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.image import imread
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

HALO_ESCURO = [patheffects.withStroke(linewidth=2.6, foreground="#1A1A1A")]
HALO_CLARO = [patheffects.withStroke(linewidth=2.6, foreground="white")]


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


# --------------------------------------------------------------------------- #
# Título e rosa dos ventos
# --------------------------------------------------------------------------- #


def caixa_titulo(fig: Figure, perfil: PerfilPagina, texto: str) -> None:
    """Caixa branca com borda preta, texto serifado bold — topo-centro."""
    ax = _eixo(fig, perfil, perfil.titulo, zorder=25)
    ax.add_patch(
        Rectangle(
            (0.0, 0.0),
            1.0,
            1.0,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor=COR_MOLDURA,
            linewidth=1.0,
        )
    )
    ax.text(
        0.5,
        0.5,
        texto,
        ha="center",
        va="center",
        fontsize=perfil.pt_titulo,
        fontweight="bold",
        family="DejaVu Serif",
        color="black",
    )


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
                linewidth=0.5,
            )
        )
        ax.add_patch(
            PolygonPatch(
                [(cx, cy), (cx2, cy2), (px, py)],
                closed=True,
                facecolor="#333333",
                edgecolor="black",
                linewidth=0.5,
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
            fontsize=5.5,
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
        ax.spines[lado].set_linewidth(1.2)
        ax.spines[lado].set_color(COR_MOLDURA)
    ax.set_xticks([])
    ax.set_yticks([])

    tam_tick = 0.008  # fração do eixo
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
            ax.plot(
                [pos, pos],
                [base, base + sentido * tam_tick],
                transform=trans_x,
                color=COR_MOLDURA,
                linewidth=0.8,
                clip_on=False,
                zorder=30,
            )
            ax.text(
                pos,
                base + sentido * tam_tick * 1.6,
                item["rotulo"],
                transform=trans_x,
                ha="center",
                va=va,
                fontsize=perfil.pt_grade,
                color="black",
                clip_on=False,
                zorder=30,
            )
        if com_linhas:
            ax.plot(
                [item["inferior"], item["superior"]],
                [y0, y1],
                color="#999999",
                linewidth=0.4,
                zorder=6,
            )

    for item in grade.get("y", []):
        for chave, base, sentido, ha, rot in (
            ("esquerda", 0.0, -1.0, "right", 90),
            ("direita", 1.0, 1.0, "left", 90),
        ):
            pos = item[chave]
            if not (y0 <= pos <= y1):
                continue
            ax.plot(
                [base, base + sentido * tam_tick],
                [pos, pos],
                transform=trans_y,
                color=COR_MOLDURA,
                linewidth=0.8,
                clip_on=False,
                zorder=30,
            )
            ax.text(
                base + sentido * tam_tick * 1.6,
                pos,
                item["rotulo"],
                transform=trans_y,
                ha=ha,
                va="center",
                rotation=90,
                rotation_mode="anchor",
                fontsize=perfil.pt_grade,
                color="black",
                clip_on=False,
                zorder=30,
            )
        if com_linhas:
            ax.plot(
                [x0, x1],
                [item["esquerda"], item["direita"]],
                color="#999999",
                linewidth=0.4,
                zorder=6,
            )


def rotulo_imovel(ax: Axes, ponto: tuple[float, float], texto: str, *, pt: float = 9.0) -> None:
    """Nome do imóvel no centroide, branco com halo escuro, acima das hachuras."""
    ax.text(
        ponto[0],
        ponto[1],
        texto,
        ha="center",
        va="center",
        fontsize=pt,
        color="white",
        fontweight="bold",
        path_effects=HALO_ESCURO,
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
    passo = _passo_linha(perfil.pt_metadados, perfil.metadados.altura)
    # Ancorado na **base** da caixa, como no modelo: um bloco com menos linhas
    # sobe a partir do rodapé, em vez de esticar para preencher a caixa.
    y = passo * (len(linhas) + 0.6)

    ax.text(
        0.5,
        y,
        titulo,
        ha="center",
        va="center",
        fontsize=perfil.pt_metadados + 1,
        fontweight="bold",
        color="black",
    )
    y -= passo

    for par in linhas:
        rotulo = str(par.get("rotulo") or "").strip()
        valor = str(par.get("valor") or "").strip()
        # Rótulo em negrito + valor normal, com o par inteiro centralizado:
        # dois `text` ancorados no meio, um à direita e outro à esquerda.
        ax.text(
            0.5,
            y,
            f"{rotulo}: ",
            ha="right",
            va="center",
            fontsize=perfil.pt_metadados,
            fontweight="bold",
            color="black",
        )
        ax.text(
            0.5,
            y,
            f" {valor}",
            ha="left",
            va="center",
            fontsize=perfil.pt_metadados,
            color="black",
        )
        y -= passo

    return len(linhas)


LARGURA_CHAR_MM_POR_PT = 0.2
"""Largura média de caractere da DejaVu Sans: ~0,55 em × 0,3528 mm/pt."""


def _quebrar(texto: str, largura_mm: float, pt: float) -> str:
    """Quebra o rótulo para caber na largura da caixa, em linhas de palavras."""
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

    largura_swatch = 0.20
    largura_texto_mm = perfil.legenda.largura * (1.0 - largura_swatch - 0.06)

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

    # Ancorada na base da caixa, como o bloco de metadados.
    y = passo_linha * (total_linhas - 0.3)

    ax.text(
        0.0,
        y,
        perfil.titulo_legenda,
        ha="left",
        va="center",
        fontsize=pt + 1,
        fontweight="bold",
        color="black",
    )
    y -= passo_linha

    for item, rotulo, n_linhas in zip(itens, rotulos, linhas_por_item):
        estilo = obter_estilo(item.get("estilo"))
        face = estilo.get("cor_preenchimento")
        centro = y - passo_linha * (n_linhas - 1) / 2.0
        altura_swatch = passo_linha * 0.6
        ax.add_patch(
            Rectangle(
                (0.0, centro - altura_swatch / 2),
                largura_swatch,
                altura_swatch,
                transform=ax.transAxes,
                facecolor=face if face else "none",
                edgecolor=estilo["cor_linha"],
                linewidth=1.6,
            )
        )
        ax.text(
            largura_swatch + 0.06,
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
    caixa = perfil.minimapa
    ax = fig.add_axes(perfil.fracao(caixa), zorder=25)
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ("left", "right", "top", "bottom"):
        ax.spines[lado].set_visible(True)
        ax.spines[lado].set_linewidth(1.0)
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
            linewidth=0.25,
        )
    _desenhar_shape(ax, alvo_shape, facecolor=COR_MUNICIPIO_ALVO, edgecolor="black", linewidth=0.5)

    ax.set_xlim(vista[0], vista[2])
    ax.set_ylim(vista[1], vista[3])
    ax.set_aspect("equal", adjustable="box")

    if municipio:
        ax.text(
            (bx0 + bx1) / 2,
            (by0 + by1) / 2,
            municipio,
            ha="center",
            va="center",
            fontsize=6.5,
            fontweight="bold",
            color="black",
            path_effects=HALO_CLARO,
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
                linewidth=1.4,
                zorder=14,
            )
        )
        info["retangulo_ok"] = True
        info["retangulo_lonlat"] = [lon, lat]

        # Linha-guia em L, desenhada na página (sai do inset e sobe até o quadro).
        x_fig, y_fig = ax.transAxes.inverted().transform((0, 0))  # força o cálculo do eixo
        del x_fig, y_fig
        px_dado = ax.transData.transform((lon + lado_x / 2, lat + lado_y / 2))
        px_fig = fig.transFigure.inverted().transform(px_dado)
        alvo_x, alvo_y = mm_para_figura(perfil, perfil.mapa.x0 + 1.5, perfil.mapa.y1)
        ax_pagina = eixo_pagina(fig)
        ax_pagina.plot(
            [px_fig[0], px_fig[0], alvo_x],
            [px_fig[1], alvo_y, alvo_y],
            color=COR_GUIA,
            linewidth=0.9,
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
            selo.spines[lado].set_linewidth(0.8)
            selo.spines[lado].set_color(COR_MOLDURA)
        selo.set_facecolor("white")
        import shapefile as _shp

        reader = _shp.Reader(str(shp_ufs))
        campos = [f[0] for f in reader.fields[1:]]
        i_sigla = campos.index("sigla_uf") if "sigla_uf" in campos else 0
        for sr in reader.iterShapeRecords():
            if str(sr.record[i_sigla]).upper() != uf.upper():
                continue
            _desenhar_shape(selo, sr.shape, facecolor=COR_UF, edgecolor="black", linewidth=0.4)
            ux0, uy0, ux1, uy1 = sr.shape.bbox
            selo.set_xlim(ux0, ux1)
            selo.set_ylim(uy0, uy1)
            selo.set_aspect("equal", adjustable="box")
            _desenhar_shape(selo, alvo_shape, facecolor=COR_MUNICIPIO_ALVO, edgecolor="black", linewidth=0.4)
            selo.text(
                0.5,
                0.12,
                uf.upper(),
                transform=selo.transAxes,
                ha="center",
                va="center",
                fontsize=6.0,
                fontweight="bold",
                path_effects=HALO_CLARO,
            )
            info["selo_uf_ok"] = True
            break

    return info
