"""Renderizador nativo de PDF — padrão Harmonia sem ArcGIS nenhum (F1-05).

Desenha a página inteira: quadro do mapa com grade DMS, caixa de título, rosa
dos ventos, camadas nos estilos oficiais, rótulo do imóvel e a faixa inferior
(minimapa · metadados · legenda · logo), mais a tabela de quantitativos quando
o MapSpec pede.

O que ele **não** promete: identidade pixel a pixel com o ArcMap. O que ele
promete: a mesma anatomia, medida de `planos/01-padrao-imap-harmonia.md`, em
qualquer máquina — inclusive no CI Linux, onde é o único motor disponível.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FAMILIA_FONTE = ["Arial", "Liberation Sans", "Nimbus Sans", "DejaVu Sans"]
"""O ArcMap compõe os modelos em **Arial**. A Liberation Sans tem as mesmas
métricas e existe em qualquer Linux; a Nimbus Sans é o terceiro plano.

Não é preciosismo tipográfico: com DejaVu Sans (mais larga) o bloco de
metadados dos mapas paisagem saía ~9 mm mais largo que o do modelo, o bastante
para estourar a tolerância de 6 mm da anatomia em 5 dos 20 mapas."""

matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = FAMILIA_FONTE + list(
    matplotlib.rcParams.get("font.sans-serif", [])
)
# PDF de entrega: Type 42 (TrueType subset). O default do matplotlib é Type 3, em que cada
# glifo vira um procedimento vetorial — o texto continua extraível, mas a fonte não vai
# embutida de verdade (ext `n/a` no `get_fonts`), o que pré-impressora recusa e alguns
# leitores tratam como desenho. Type 42 embute o programa da fonte e mantém o texto texto.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
from matplotlib.image import imread  # noqa: E402
from matplotlib.patches import Polygon as PolygonPatch  # noqa: E402
from shapely.ops import transform  # noqa: E402

from mapasfacil_nucleo.artefatos import PASTA_PREVIEW  # noqa: E402
from mapasfacil_nucleo.camadas import ibge as ibge_mod  # noqa: E402
from mapasfacil_nucleo.config import raiz_repositorio  # noqa: E402
from mapasfacil_nucleo.fsguard import WorkspaceGuard  # noqa: E402
from mapasfacil_nucleo.motores import basemap as basemap_mod  # noqa: E402
from mapasfacil_nucleo.motores import blocos, grade_dms, perfil_pagina  # noqa: E402
from mapasfacil_nucleo.motores.estilos import obter as obter_estilo  # noqa: E402
from mapasfacil_nucleo.validacao.relatorio import gerar, salvar  # noqa: E402
from mapasfacil_nucleo.workspace.shapefile import (  # noqa: E402
    _abrir_reader,
    _shapes_para_geometrias,
    inspecionar,
)

DPI_PREVIEW = 72
"""Rasterização intermediária: leve de propósito — é preview, não entrega."""

DPI_PDF = 300
"""Export final. Abaixo disso a tabela de 600 dpi efetivos borra visivelmente."""

MARGEM_ENQUADRAMENTO = 1.12
"""Folga aplicada ao bbox do imóvel quando a escala é `auto`."""

DATUM_POR_EPSG: dict[int, str] = {
    31982: "SIRGAS 2000 UTM 22 S",
    31981: "SIRGAS 2000 UTM 21 S",
    31983: "SIRGAS 2000 UTM 23 S",
    3857: "WGS 84 Pseudo-Mercator",
    4674: "SIRGAS 2000",
    4326: "WGS 84",
}

LOGO_PADRAO = "shared/templates/recursos/logo_imap_tom_escuro.png"


# --------------------------------------------------------------------------- #
# Leitura de camadas
# --------------------------------------------------------------------------- #


def _resolver_fonte_local(fonte: str, fontes_idx: dict[str, str]) -> Path | None:
    if not fonte.startswith("local."):
        return None
    chave = fonte.split(".", 1)[1]
    rel = fontes_idx.get(chave)
    return Path(rel) if rel else None


def _epsg_do_mapspec(mapspec: dict[str, Any], perfil: perfil_pagina.PerfilPagina) -> int:
    crs = mapspec.get("crs") or perfil.crs_padrao
    try:
        return int(str(crs).split(":")[-1])
    except (TypeError, ValueError):
        return int(perfil.crs_padrao.split(":")[-1])


def _carregar_camadas(
    mapspec: dict[str, Any],
    fontes_idx: dict[str, str],
    guard: WorkspaceGuard,
    epsg_alvo: int,
) -> list[dict[str, Any]]:
    """Geometrias já reprojetadas para o CRS do quadro, na ordem de desenho."""
    from pyproj import Transformer

    carregadas: list[dict[str, Any]] = []
    for camada in mapspec.get("camadas") or []:
        fonte = camada.get("fonte", "")
        rel = _resolver_fonte_local(fonte, fontes_idx)
        if not rel:
            continue
        caminho = guard.resolver(rel)
        if not caminho.is_file():
            continue
        meta = inspecionar(caminho)
        epsg_origem = meta.crs.get("epsg") or 4674
        reader, _enc = _abrir_reader(caminho)
        geometrias = _shapes_para_geometrias(reader)
        if epsg_origem != epsg_alvo:
            transformer = Transformer.from_crs(
                f"EPSG:{epsg_origem}", f"EPSG:{epsg_alvo}", always_xy=True
            )
            geometrias = [transform(transformer.transform, g) for g in geometrias]
        carregadas.append(
            {
                "id": camada.get("id"),
                "estilo": camada.get("estilo"),
                "legenda": camada.get("legenda") or camada.get("nome_no_mxd"),
                "ordem": camada.get("ordem", 50),
                "rotulo_texto": camada.get("rotulo_texto"),
                "geometrias": geometrias,
            }
        )
    return carregadas


def _poligonos(geom: Any) -> list[Any]:
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return []


def _plotar(ax, camadas: list[dict[str, Any]]) -> int:
    """Desenha as camadas. Menor `ordem` fica por cima (perímetro sobre hachura)."""
    desenhadas = 0
    for camada in sorted(camadas, key=lambda c: c.get("ordem", 50), reverse=True):
        estilo = obter_estilo(camada.get("estilo"))
        face = estilo.get("cor_preenchimento")
        largura_hachura = estilo.get("largura_hachura")
        for geom in camada["geometrias"]:
            for poly in _poligonos(geom):
                xs, ys = poly.exterior.xy
                patch = PolygonPatch(
                    list(zip(xs, ys)),
                    closed=True,
                    facecolor=face if face else "none",
                    edgecolor=estilo["cor_linha"],
                    linewidth=estilo["largura"],
                    hatch=estilo.get("hachura"),
                    zorder=10,
                )
                if largura_hachura is not None and hasattr(patch, "set_hatch_linewidth"):
                    # Contorno grosso e hachura fina, como o símbolo do ArcMap (modelos da
                    # Aline): no matplotlib a hachura herdava a espessura global.
                    patch.set_hatch_linewidth(float(largura_hachura))
                ax.add_patch(patch)
                desenhadas += 1
    return desenhadas


def _tem_geometria(camada: dict[str, Any]) -> bool:
    return any(not g.is_empty for g in camada.get("geometrias") or [])


# --------------------------------------------------------------------------- #
# Enquadramento
# --------------------------------------------------------------------------- #


def _bbox_camadas(camadas: list[dict[str, Any]], id_preferido: str = "perimetro") -> tuple[float, float, float, float] | None:
    alvo = [c for c in camadas if c.get("id") == id_preferido] or camadas
    caixas = [g.bounds for c in alvo for g in c["geometrias"] if not g.is_empty]
    if not caixas:
        return None
    return (
        min(b[0] for b in caixas),
        min(b[1] for b in caixas),
        max(b[2] for b in caixas),
        max(b[3] for b in caixas),
    )


def _escala_numerica(escala: Any) -> float | None:
    if isinstance(escala, (int, float)) and escala > 0:
        return float(escala)
    if isinstance(escala, str):
        texto = escala.strip().lower().replace("1:", "").replace(".", "").replace(" ", "")
        if texto.isdigit():
            return float(texto)
    return None


def _extent(
    mapspec: dict[str, Any],
    camadas: list[dict[str, Any]],
    perfil: perfil_pagina.PerfilPagina,
) -> tuple[tuple[float, float, float, float], float | None]:
    """Extent que preenche o quadro **exatamente**, e a escala efetiva."""
    caixa_mapa = perfil.mapa
    razao_pagina = caixa_mapa.altura / caixa_mapa.largura

    declarado = mapspec.get("extent")
    if isinstance(declarado, dict) and all(k in declarado for k in ("xmin", "ymin", "xmax", "ymax")):
        base = (
            float(declarado["xmin"]),
            float(declarado["ymin"]),
            float(declarado["xmax"]),
            float(declarado["ymax"]),
        )
    else:
        base = _bbox_camadas(camadas) or (0.0, 0.0, 1.0, 1.0)

    cx = (base[0] + base[2]) / 2.0
    cy = (base[1] + base[3]) / 2.0

    escala = _escala_numerica(mapspec.get("escala"))
    if escala:
        # mm de página → metros no terreno: a escala manda no enquadramento.
        largura = caixa_mapa.largura / 1000.0 * escala
        altura = caixa_mapa.altura / 1000.0 * escala
    else:
        largura = max(base[2] - base[0], 1.0) * MARGEM_ENQUADRAMENTO
        altura = max(base[3] - base[1], 1.0) * MARGEM_ENQUADRAMENTO
        # Ajusta ao formato do quadro sem cortar nada.
        if altura / largura < razao_pagina:
            altura = largura * razao_pagina
        else:
            largura = altura / razao_pagina
        escala = largura / (caixa_mapa.largura / 1000.0)

    return (cx - largura / 2, cy - altura / 2, cx + largura / 2, cy + altura / 2), escala


# --------------------------------------------------------------------------- #
# Metadados e legenda
# --------------------------------------------------------------------------- #


def _bbox_4326(extent: tuple[float, float, float, float], epsg: int) -> list[float] | None:
    """Extent projetado → `[oeste, sul, leste, norte]` em graus (o palco desenha em 4326)."""
    try:
        from pyproj import Transformer

        transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
        oeste, sul = transformer.transform(extent[0], extent[1])
        leste, norte = transformer.transform(extent[2], extent[3])
        return [
            round(min(oeste, leste), 6),
            round(min(sul, norte), 6),
            round(max(oeste, leste), 6),
            round(max(sul, norte), 6),
        ]
    except Exception:  # noqa: BLE001 — sem pyproj o palco perde o foco, o PDF não
        return None


def _formatar_escala(escala: float | None) -> str:
    if not escala:
        return ""
    return f"1:{int(round(escala)):,}".replace(",", ".")


def _resolver_metadados(
    mapspec: dict[str, Any],
    *,
    epsg: int,
    escala: float | None,
    basemap: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Resolve os `auto` do bloco a partir do que o mapa realmente usou.

    Quando o basemap que entrou não é o que o modelo declarava, o bloco conta a
    verdade: o metadado descreve a imagem que está no papel, não a que se
    pretendia usar.
    """
    basemap = basemap or {}
    pares: list[dict[str, Any]] = []
    for item in mapspec.get("metadados") or []:
        rotulo = str(item.get("rotulo") or "").strip()
        valor = item.get("valor")
        chave = rotulo.lower()

        if isinstance(valor, str) and valor.strip().lower() == "auto":
            if chave.startswith("datum"):
                valor = DATUM_POR_EPSG.get(epsg, f"EPSG:{epsg}")
            elif chave.startswith("escala"):
                valor = _formatar_escala(escala)
            elif chave.startswith(("satélite", "satelite", "base")) and basemap.get("ok"):
                valor = str(basemap.get("fonte") or "")
            elif chave.startswith("data") and basemap.get("ano"):
                # A data é a da imagem que entrou, não a que se pediu: quando o
                # ano não existe no acervo da SEMA o basemap cai no anterior, e
                # repetir o ano pedido seria escrever uma data falsa no mapa.
                valor = str(basemap.get("ano"))
            else:
                valor = ""
        elif basemap.get("ok") and chave.startswith(("satélite", "satelite")):
            fonte = str(basemap.get("fonte") or "")
            # O modelo diz "SPOT" e a imagem que entrou é o "Mosaico SPOT 2008 (SEPLAN)":
            # é a mesma coisa, fica o texto curto do modelo. Só troca quando a imagem é
            # outra (pediu PLANET, caiu no Esri) — aí o bloco conta a verdade.
            declarado = str(valor or "").strip()
            if not declarado or declarado.casefold() not in fonte.casefold():
                valor = fonte or valor

        pares.append({"rotulo": rotulo, "valor": valor})
    return pares


def _itens_legenda(
    camadas: list[dict[str, Any]], ajuste: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Itens da legenda: só camada que **aparece** no mapa.

    Uma classe sem feição (o `AUAS` vazio do SIMCAR) entrava na legenda com a cor dela e
    nada no mapa — o leitor procurava o desmate que não existe (teste_22). O modelo pode
    fixar a ordem (`ajustes_layout.legenda.ordem`, ids de camada) e acrescentar itens que
    não são camada do quadro principal (`extras`: limites do minimapa).
    """
    ajuste = ajuste if isinstance(ajuste, dict) else {}
    ordem_ids = [str(i) for i in ajuste.get("ordem") or []]

    def chave(c: dict[str, Any]) -> tuple[int, int]:
        cid = str(c.get("id") or "")
        return (ordem_ids.index(cid) if cid in ordem_ids else len(ordem_ids), int(c.get("ordem", 50)))

    itens: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for camada in sorted(camadas, key=chave):
        rotulo = str(camada.get("legenda") or "").strip()
        if not rotulo or rotulo in vistos or not _tem_geometria(camada):
            continue
        vistos.add(rotulo)
        itens.append({"rotulo": rotulo, "estilo": camada.get("estilo")})
    for extra in ajuste.get("extras") or []:
        if not isinstance(extra, dict):
            continue
        rotulo = str(extra.get("rotulo") or "").strip()
        if rotulo and rotulo not in vistos:
            vistos.add(rotulo)
            itens.append({"rotulo": rotulo, "estilo": extra.get("estilo")})
    return itens


# --------------------------------------------------------------------------- #
# Elementos por cima do quadro do mapa
# --------------------------------------------------------------------------- #


def _ajuste(mapspec: dict[str, Any], elemento: str) -> dict[str, Any]:
    ajustes = mapspec.get("ajustes_layout") or {}
    valor = ajustes.get(elemento) if isinstance(ajustes, dict) else None
    return valor if isinstance(valor, dict) else {}


def _perfil_com_ajustes(
    perfil: perfil_pagina.PerfilPagina, mapspec: dict[str, Any]
) -> perfil_pagina.PerfilPagina:
    """Corpo de letra que o modelo fixa (`ajustes_layout.legenda.pt`/`pt_titulo`,
    `ajustes_layout.grade.pt`), em pt de A4 — cresce com a folha como o resto (D31)."""
    from dataclasses import replace

    mudar: dict[str, float] = {}
    legenda = _ajuste(mapspec, "legenda")
    grade = _ajuste(mapspec, "grade")
    for chave, campo, origem in (
        ("pt", "pt_legenda", legenda),
        ("pt_titulo", "pt_legenda_titulo", legenda),
        ("pt", "pt_grade", grade),
    ):
        valor = origem.get(chave)
        if isinstance(valor, (int, float)) and 3.0 <= float(valor) <= 30.0:
            mudar[campo] = perfil.escalado(float(valor))
    return replace(perfil, **mudar) if mudar else perfil


def _rotulos_cabem(
    itens: list[dict[str, Any]], chave: str, comprimento_mm: float, span: float, pt: float
) -> bool:
    """Os rótulos de uma borda não se encostam (≥ 3 mm entre um e outro)?"""
    if len(itens) < 2 or span <= 0:
        return True
    posicoes = sorted(float(i[chave]) for i in itens)
    menor_vao = min(b - a for a, b in zip(posicoes, posicoes[1:])) * comprimento_mm / span
    maior = max(blocos.largura_texto_mm(str(i["rotulo"]), pt) for i in itens)
    return menor_vao >= maior + 3.0


def _grade_legivel(
    extent: tuple[float, float, float, float],
    epsg: int,
    perfil: perfil_pagina.PerfilPagina,
    alvo: float | None,
) -> dict[str, Any]:
    """Grade com a densidade do modelo, recuando enquanto os rótulos se encostarem.

    O passo é o mesmo nos dois eixos (o do lado menor). Com 8 rótulos pedidos, o retrato
    da Aline fica igual ao dela, mas a paisagem dava 14 rótulos encostados no eixo X.
    """
    x0, y0, x1, y1 = extent
    while True:
        grade = grade_dms.calcular(extent, epsg_projetado=epsg, rotulos_alvo=alvo)
        cabe = _rotulos_cabem(
            grade["x"], "inferior", perfil.mapa.largura, x1 - x0, perfil.pt_grade
        ) and _rotulos_cabem(grade["y"], "esquerda", perfil.mapa.altura, y1 - y0, perfil.pt_grade)
        if cabe or alvo is None:
            return grade
        alvo = alvo - 1.0 if alvo - 1.0 > grade_dms.ALVO_IDEAL else None


def _formatar_ha(valor: Any, casas: int = 4) -> str:
    if not isinstance(valor, (int, float)):
        return "–"
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def linhas_quadro_resumo(mapspec: dict[str, Any], areas: dict[str, Any] | None) -> list[str]:
    """Texto do quadro de resumo com as áreas **calculadas dos shapes** (regra do Álvaro).

    O modelo escreve as linhas com marcadores: `{avn_ha}`, `{ac_ha}`, `{area_total_ha}`,
    `{auas_ha}` (os mesmos campos dos quantitativos) e `{ano}`.
    """
    ajuste = _ajuste(mapspec, "quadro_resumo")
    modelo = ajuste.get("linhas") or []
    casas = int((mapspec.get("tabela") or {}).get("casas_decimais") or 4)
    valores = {k: _formatar_ha(v, casas) for k, v in (areas or {}).items()}
    valores.setdefault("ano", str(ajuste.get("ano") or ""))
    linhas: list[str] = []
    for linha in modelo:
        texto = str(linha)
        for chave, valor in valores.items():
            texto = texto.replace("{" + chave + "}", valor)
        linhas.append(texto)
    return linhas


def _geometria_alvo(camadas: list[dict[str, Any]]) -> Any | None:
    """O que não pode ficar embaixo de título, rosa, tabela ou quadro: o imóvel."""
    from shapely.ops import unary_union

    alvo = [c for c in camadas if c.get("id") == "perimetro" and _tem_geometria(c)]
    alvo = alvo or [c for c in camadas if _tem_geometria(c)]
    geoms = [g if g.is_valid else g.buffer(0) for c in alvo for g in c["geometrias"] if not g.is_empty]
    if not geoms:
        return None
    try:
        return unary_union(geoms)
    except Exception:  # noqa: BLE001 — geometria ruim não derruba o mapa
        return None


def _caixa_no_mapa(
    caixa: perfil_pagina.Caixa,
    extent: tuple[float, float, float, float],
    perfil: perfil_pagina.PerfilPagina,
    folga_mm: float,
):
    """Caixa da página (mm) → retângulo nas coordenadas do mapa."""
    from shapely.geometry import box

    q = perfil.mapa
    sx = (extent[2] - extent[0]) / q.largura
    sy = (extent[3] - extent[1]) / q.altura
    x0 = extent[0] + (max(caixa.x0, q.x0) - folga_mm - q.x0) * sx
    x1 = extent[0] + (min(caixa.x1, q.x1) + folga_mm - q.x0) * sx
    y_topo = extent[3] - (max(caixa.y0, q.y0) - folga_mm - q.y0) * sy
    y_base = extent[3] - (min(caixa.y1, q.y1) + folga_mm - q.y0) * sy
    return box(min(x0, x1), min(y_base, y_topo), max(x0, x1), max(y_base, y_topo))


def _afastar_de_sobreposicoes(
    extent: tuple[float, float, float, float],
    alvo: Any,
    caixas: list[perfil_pagina.Caixa],
    perfil: perfil_pagina.PerfilPagina,
) -> tuple[tuple[float, float, float, float], bool]:
    """Enquadramento em que nenhum elemento sobre o mapa cobre o imóvel.

    No teste_22 a tabela de quantitativos ficava por cima do mapa; no modelo da Aline o
    quadro de resumo ocupa o canto inferior-direito. Primeiro tenta **deslizar** o mapa na
    vertical (mantém a escala); se não basta, **afasta** a câmera aos poucos (até 1,7×).
    Devolve o extent e se ficou livre.
    """
    if alvo is None or not caixas:
        return extent, True
    folga = perfil.escalado(1.5)

    def livre(ext: tuple[float, float, float, float]) -> bool:
        if not _contem(ext, alvo.bounds):
            return False
        return not any(alvo.intersects(_caixa_no_mapa(c, ext, perfil, folga)) for c in caixas)

    if livre(extent):
        return extent, True
    cx = (extent[0] + extent[2]) / 2.0
    cy = (extent[1] + extent[3]) / 2.0
    largura = extent[2] - extent[0]
    altura = extent[3] - extent[1]
    for zoom in [1.0] + [1.05**i for i in range(1, 12)]:
        w, h = largura * zoom, altura * zoom
        for desloc in (0.0, 0.04, -0.04, 0.08, -0.08, 0.12, -0.12, 0.16, -0.16):
            ccy = cy + desloc * h
            cand = (cx - w / 2, ccy - h / 2, cx + w / 2, ccy + h / 2)
            if livre(cand):
                return cand, True
    return extent, False


def _contem(ext: tuple[float, float, float, float], bounds: tuple[float, float, float, float]) -> bool:
    return ext[0] <= bounds[0] and ext[1] <= bounds[1] and ext[2] >= bounds[2] and ext[3] >= bounds[3]


def _centroide_lonlat(camadas: list[dict[str, Any]], epsg: int) -> tuple[float, float] | None:
    from pyproj import Transformer

    bbox = _bbox_camadas(camadas)
    if bbox is None:
        return None
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    para_geo = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = para_geo.transform(cx, cy)
    return float(lon), float(lat)


# --------------------------------------------------------------------------- #
# Preview e tabela
# --------------------------------------------------------------------------- #


def _deve_sobrepor_tabela(mapspec: dict[str, Any]) -> bool:
    layout = mapspec.get("elementos_layout") or {}
    if "tabela" in layout:
        return bool(layout["tabela"])
    return bool(mapspec.get("tabela"))


def _sobrepor_png_tabela(fig, perfil: perfil_pagina.PerfilPagina, png_tabela: Path) -> bool:
    if not png_tabela.is_file():
        return False
    ax_tab = fig.add_axes(perfil.fracao(perfil.tabela), zorder=28)
    try:
        img = imread(str(png_tabela))
    except Exception:  # noqa: BLE001 — PNG ilegível não derruba o mapa
        return False
    ax_tab.imshow(img, aspect="auto", interpolation="bilinear")
    ax_tab.set_xticks([])
    ax_tab.set_yticks([])
    for spine in ax_tab.spines.values():
        spine.set_visible(False)
    return True


def _salvar_preview(fig, guard: WorkspaceGuard, ordem: int) -> str:
    destino = guard.resolver(f"{PASTA_PREVIEW}/parcial_{ordem:02d}.png", escrita=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, format="png", dpi=DPI_PREVIEW)
    return str(destino.relative_to(guard.raiz))


def _ligado(mapspec: dict[str, Any], chave: str, padrao: bool = True) -> bool:
    layout = mapspec.get("elementos_layout") or {}
    if chave in layout:
        return bool(layout[chave])
    return padrao


# --------------------------------------------------------------------------- #
# Motor
# --------------------------------------------------------------------------- #


def gerar_pdf_minimo(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
    png_tabela: Path | None = None,
    ao_preview: Callable[[str, str], None] | None = None,
    progresso: Any = None,
    quantitativos: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Desenha o mapa no padrão Harmonia e exporta PDF (+ PNG da página).

    `ao_preview(caminho_rel, etapa)` alimenta `job.artefato_parcial` do tipo
    `preview_png`. Sem callback nada é rasterizado além da entrega: quem chama
    como biblioteca não paga por preview que ninguém vê.
    """
    saida_cfg = mapspec.get("saida") or {}
    pasta_nome = saida_cfg.get("pasta", "Mapas")
    nome_base = saida_cfg.get("nome_base", "mapa")
    pasta = guard.resolver(pasta_nome, escrita=True)
    pdf_path = pasta / f"{nome_base}.pdf"

    perfil = _perfil_com_ajustes(_perfil_do_mapspec(mapspec), mapspec)
    epsg = _epsg_do_mapspec(mapspec, perfil)

    camadas = _carregar_camadas(mapspec, fontes_idx, guard, epsg)
    extent, escala = _extent(mapspec, camadas, perfil)

    # Elementos que ficam **por cima** do quadro do mapa: planejados antes do enquadramento
    # para o imóvel não ficar embaixo deles (só com escala automática — escala pedida pelo
    # usuário é respeitada e vira aviso).
    titulo_texto = str(mapspec.get("titulo") or "")
    plano_titulo = (
        blocos.planejar_titulo(perfil, titulo_texto, _ajuste(mapspec, "titulo"))
        if _ligado(mapspec, "titulo_caixa")
        else None
    )
    areas_quadro = dict((quantitativos or {}).get("areas") or {})
    plano_quadro = None
    if _ligado(mapspec, "quadro_resumo", padrao=False):
        plano_quadro = blocos.planejar_quadro_resumo(
            perfil, linhas_quadro_resumo(mapspec, areas_quadro), _ajuste(mapspec, "quadro_resumo")
        )
    caixas_sobre_mapa: list[perfil_pagina.Caixa] = []
    if plano_titulo is not None:
        caixas_sobre_mapa.append(plano_titulo.caixa)
    if _ligado(mapspec, "norte"):
        caixas_sobre_mapa.append(perfil.rosa)
    if png_tabela is not None and _deve_sobrepor_tabela(mapspec):
        caixas_sobre_mapa.append(perfil.tabela)
    if plano_quadro is not None:
        caixas_sobre_mapa.append(plano_quadro.caixa)
    imovel_livre = True
    escala_automatica = not _escala_numerica(mapspec.get("escala")) and not isinstance(
        mapspec.get("extent"), dict
    )
    alvo_livre = _geometria_alvo(camadas)
    if escala_automatica:
        extent, imovel_livre = _afastar_de_sobreposicoes(extent, alvo_livre, caixas_sobre_mapa, perfil)
        escala = (extent[2] - extent[0]) / (perfil.mapa.largura / 1000.0)
    elif alvo_livre is not None:
        folga = perfil.escalado(1.5)
        imovel_livre = not any(
            alvo_livre.intersects(_caixa_no_mapa(c, extent, perfil, folga)) for c in caixas_sobre_mapa
        )

    # Palco (W7): o `enquadramento` é emitido quando a escala deixou de ser dúvida; a `folha`
    # quando o mapa já é página. Daqui para baixo cada elemento posicionado vira
    # `layout.elemento` — nesta ordem, que é a ordem de desenho.
    motion_mod = None
    folha_dict: dict[str, Any] = {}
    palco_layout: dict[str, Any] | None = None
    bbox_4326: list[float] | None = None
    if progresso is not None and getattr(progresso, "emite_eventos", False) and progresso.job_id:
        from mapasfacil_nucleo import motion as motion_mod

        folha_dict = {
            "formato": str((mapspec.get("folha") or {}).get("formato") or "A4").upper(),
            "orientacao": perfil.orientacao,
            "largura_mm": perfil.largura_mm,
            "altura_mm": perfil.altura_mm,
        }
        bbox_4326 = _bbox_4326(extent, epsg)
        if bbox_4326 is not None:
            quadro = (perfil.mapa.largura, perfil.mapa.altura)
            try:
                progresso.foco(
                    "enquadramento",
                    bbox_4326,
                    _formatar_escala(escala) or "escala automática",
                    "calculo_escala",
                    escala=int(round(escala)) if escala else None,
                    crs_mapa=f"EPSG:{epsg}",
                    quadro_mm=quadro,
                )
                progresso.foco(
                    "folha",
                    bbox_4326,
                    f"{folha_dict['formato']} {folha_dict['orientacao']}",
                    "perfil_pagina",
                    quadro_mm=quadro,
                )
            except Exception as exc:  # noqa: BLE001 — palco nunca derruba o PDF
                progresso.log(f"palco: foco de enquadramento/folha recusado ({exc})")
        ligados = [
            e
            for e in motion_mod.elementos_na_ordem(motion_mod.ELEMENTOS)
            if _ligado(mapspec, e, padrao=(e != "grade_linhas"))
        ]
        if not (png_tabela is not None and _deve_sobrepor_tabela(mapspec)):
            ligados = [e for e in ligados if e != "tabela"]
        palco_layout = {"total": len(ligados), "n": 0, "ligados": set(ligados)}

    def _elemento(nome: str, *, conteudo: Any = None, caminho: Any = None) -> None:
        """Emite `layout.elemento` se o elemento foi ligado neste MapSpec."""
        if palco_layout is None or progresso is None or motion_mod is None:
            return
        if nome not in palco_layout["ligados"]:
            return
        palco_layout["n"] += 1
        try:
            progresso.elemento(
                elemento=nome,
                sequencia=palco_layout["n"],
                total=palco_layout["total"],
                folha=folha_dict,
                caixa_mm=motion_mod.caixa_do_elemento(perfil, nome),
                conteudo=conteudo,
                caminho=caminho,
            )
        except Exception as exc:  # noqa: BLE001
            progresso.log(f"palco: elemento {nome} recusado ({exc})")

    fig = plt.figure(figsize=perfil.figsize_pol)
    fig.patch.set_facecolor("white")

    ax = fig.add_axes(perfil.fracao(perfil.mapa), zorder=10)
    ax.set_xlim(extent[0], extent[2])
    ax.set_ylim(extent[1], extent[3])
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor("white")

    # Imagem de fundo primeiro: tudo o mais é desenhado por cima dela.
    info_basemap = basemap_mod.buscar(
        mapspec.get("basemap"),
        guard=guard,
        extent=extent,
        epsg=epsg,
        pasta_saida=pasta_nome,
        # W9-06: a resolução do recorte acompanha a folha (300 dpi até A2, teto em A1/A0) e o
        # `quadro_mm` permite medir o dpi efetivo para o aviso S17.
        largura=basemap_mod.largura_para_folha(perfil),
        quadro_mm=(perfil.mapa.largura, perfil.mapa.altura),
    )
    if info_basemap.get("ok"):
        try:
            ax.imshow(
                imread(str(info_basemap["caminho"])),
                extent=(extent[0], extent[2], extent[1], extent[3]),
                aspect="equal",
                interpolation="bilinear",
                zorder=1,
            )
        except Exception as exc:  # noqa: BLE001 — imagem ilegível vira degradação
            info_basemap = {
                "ok": False,
                "motivo": f"imagem baixada mas ilegível: {exc}",
                "tentativas": info_basemap.get("tentativas", []),
            }

    if (progresso is not None and getattr(progresso, "emite_eventos", False) and progresso.job_id and info_basemap.get("ok") and bbox_4326 is not None):
        # W7-08: o palco mostra o MESMO mosaico que foi para o PDF, recortado em PNG 1600 px.
        try:
            from mapasfacil_nucleo import palco as palco_mod

            pasta_raster = palco_mod.pasta_do_job(guard, str(progresso.job_id), palco_mod.SUBP_RASTER)
            info_raster = palco_mod.gravar_raster(
                Path(str(info_basemap["caminho"])),
                pasta_raster / "basemap.png",
                bbox_4326=bbox_4326,
            )
            progresso.camada(
                camada_id="basemap",
                papel="basemap",
                nome="Imagem de satelite",
                geometria="raster",
                caminho=palco_mod.relativo(info_raster["caminho"], guard),
                bbox=info_raster["bbox_4326"],
                n_feicoes=0,
                estilo={"preenchimento": None, "contorno": "#000000", "espessura_pt": 0.0},
                etapa="aplicando_layout",
            )
        except Exception as exc:  # noqa: BLE001
            progresso.log("palco: raster do basemap indisponivel (%s)" % exc)

    desenhadas = _plotar(ax, camadas)

    # Rótulo do imóvel: só o nome, branco com halo, acima das hachuras.
    rotulo = next((c for c in camadas if c.get("rotulo_texto")), None)
    if rotulo and _ligado(mapspec, "rotulo_imovel"):
        bbox_imovel = _bbox_camadas([rotulo])
        if bbox_imovel:
            blocos.rotulo_imovel(
                ax,
                ((bbox_imovel[0] + bbox_imovel[2]) / 2, (bbox_imovel[1] + bbox_imovel[3]) / 2),
                str(rotulo["rotulo_texto"]),
                perfil=perfil,
            )

    if ao_preview is not None:
        ao_preview(_salvar_preview(fig, guard, 1), "aplicando_layout")

    alvo_grade = _ajuste(mapspec, "grade").get("rotulos_por_eixo")
    grade = _grade_legivel(
        extent, epsg, perfil, float(alvo_grade) if isinstance(alvo_grade, (int, float)) else None
    )
    if _ligado(mapspec, "grade"):
        blocos.moldura_e_grade(
            ax, perfil, grade, com_linhas=_ligado(mapspec, "grade_linhas", padrao=False)
        )
        _elemento("grade")
        if _ligado(mapspec, "grade_linhas", padrao=False):
            _elemento("grade_linhas")
    else:
        blocos.moldura_e_grade(ax, perfil, {"x": [], "y": []})

    if plano_titulo is not None:
        blocos.caixa_titulo(fig, perfil, titulo_texto, plano=plano_titulo)
        _elemento("titulo_caixa", conteudo=titulo_texto)
    quadro_ok = False
    if plano_quadro is not None:
        blocos.quadro_resumo(fig, perfil, plano_quadro)
        quadro_ok = True
    if _ligado(mapspec, "norte"):
        blocos.rosa_dos_ventos(fig, perfil)
        _elemento("norte")

    metadados = _resolver_metadados(mapspec, epsg=epsg, escala=escala, basemap=info_basemap)
    linhas_meta = 0
    if _ligado(mapspec, "metadados"):
        linhas_meta = blocos.bloco_metadados(
            fig, perfil, metadados, titulo=getattr(perfil, "titulo_metadados", "METADADOS IMAGEM")
        )
        _elemento("metadados", conteudo={"linhas": linhas_meta})

    itens_legenda = _itens_legenda(camadas, _ajuste(mapspec, "legenda"))
    n_legenda = 0
    if _ligado(mapspec, "legenda"):
        n_legenda = blocos.bloco_legenda(fig, perfil, itens_legenda)
        _elemento("legenda", conteudo={"itens": n_legenda})

    info_minimapa: dict[str, Any] = {}
    if _ligado(mapspec, "minimapa"):
        imovel = mapspec.get("imovel") or {}
        municipio = (imovel.get("municipio") or {}).get("nome")
        uf = (imovel.get("municipio") or {}).get("uf")
        info_minimapa = blocos.bloco_minimapa(
            fig,
            perfil,
            municipio=municipio,
            uf=uf,
            centroide_lonlat=_centroide_lonlat(camadas, epsg),
            shp_municipios=ibge_mod.shapefile_municipios(),
            shp_ufs=ibge_mod.shapefile_ufs(),
        )

    if _ligado(mapspec, "minimapa") and info_minimapa:
        _elemento(
            "minimapa",
            conteudo={
                "municipio": info_minimapa.get("municipio"),
                "uf": info_minimapa.get("uf"),
            },
        )

    logo_ok = False
    if _ligado(mapspec, "logo"):
        logo_ok = blocos.bloco_logo(fig, perfil, raiz_repositorio() / LOGO_PADRAO)
        if logo_ok:
            _elemento("logo")

    tabela_ok = False
    if png_tabela is not None and _deve_sobrepor_tabela(mapspec):
        tabela_ok = _sobrepor_png_tabela(fig, perfil, png_tabela)
        if tabela_ok:
            _elemento("tabela")

    if ao_preview is not None:
        ao_preview(_salvar_preview(fig, guard, 2), "aplicando_layout")

    # dpi do raster por folha (W-09 §Raster): 300 dpi até A2, com teto de pixels em A1/A0.
    fig.savefig(pdf_path, format="pdf", dpi=perfil.dpi_raster(DPI_PDF))
    png_pagina = pasta / f"{nome_base}_pagina.png"
    fig.savefig(png_pagina, format="png", dpi=150)
    plt.close(fig)

    # W7-06: recortes por elemento, a partir da própria página renderizada. O palco procura
    # `layout/<elemento>.png` por convenção; sem o arquivo, mostra um bloco com o nome.
    if palco_layout is not None and progresso is not None and getattr(progresso, "emite_eventos", False):
        from mapasfacil_nucleo import palco as palco_mod

        try:
            pasta_layout = palco_mod.pasta_do_job(
                guard, str(progresso.job_id), palco_mod.SUBP_LAYOUT
            )
        except Exception as exc:  # noqa: BLE001
            progresso.log("palco: pasta de layout indisponivel (%s)" % exc)
            pasta_layout = None
        if pasta_layout is not None:
            for nome in sorted(palco_layout["ligados"]):
                try:
                    caixa = motion_mod.caixa_do_elemento(perfil, nome)
                    palco_mod.gravar_recorte_elemento(
                        png_pagina,
                        pasta_layout / ("%s.png" % nome),
                        caixa_mm=caixa,
                        largura_mm=perfil.largura_mm,
                        altura_mm=perfil.altura_mm,
                        dpi=150,
                    )
                except Exception as exc:  # noqa: BLE001
                    progresso.log("palco: recorte de %s falhou (%s)" % (nome, exc))

    hard = [
        {"id": "H09", "ok": desenhadas > 0, "mensagem": "Mapa contém geometrias desenhadas"},
        {
            "id": "H02",
            "ok": True,
            "mensagem": f"PDF gerado em A4 {perfil.orientacao} ({perfil.largura_mm:.0f}×{perfil.altura_mm:.0f} mm)",
        },
        {
            "id": "H03",
            "ok": bool(str(mapspec.get("titulo") or "").strip()) or not _ligado(mapspec, "titulo_caixa"),
            "mensagem": "Caixa de título com texto",
        },
        {
            "id": "H06",
            "ok": bool(escala),
            "mensagem": f"Escala resolvida ({_formatar_escala(escala)})",
        },
        {
            "id": "H10",
            "ok": linhas_meta > 0 or not _ligado(mapspec, "metadados"),
            "mensagem": f"Bloco de metadados com {linhas_meta} linha(s)",
        },
        {
            "id": "H16",
            "ok": not perfil_pagina.caixas_fora_da_pagina(perfil),
            "mensagem": (
                "Todos os blocos dentro da página"
                if not perfil_pagina.caixas_fora_da_pagina(perfil)
                else "Blocos fora da página: "
                + ", ".join(c["caixa"] for c in perfil_pagina.caixas_fora_da_pagina(perfil))
            ),
        },
        {
            "id": "H12",
            "ok": bool(grade.get("x")) and bool(grade.get("y")) or not _ligado(mapspec, "grade"),
            "mensagem": "Grade DMS com rótulos nos dois eixos",
        },
    ]

    soft = [
        {
            "id": "S01",
            "ok": bool(info_minimapa.get("retangulo_ok")) or not _ligado(mapspec, "minimapa"),
            "mensagem": "Retângulo do minimapa calculado sobre o centroide do imóvel",
        },
        {
            "id": "S02",
            "ok": bool(info_minimapa.get("guia_ok")) or not _ligado(mapspec, "minimapa"),
            "mensagem": "Linha-guia do minimapa até o quadro do mapa",
        },
        {
            "id": "S03",
            "ok": bool(info_minimapa.get("selo_uf_ok")) or not _ligado(mapspec, "minimapa"),
            "mensagem": "Selo da UF no minimapa",
        },
        {
            "id": "S04",
            "ok": n_legenda > 0 or not _ligado(mapspec, "legenda"),
            "mensagem": f"Legenda com {n_legenda} item(ns)",
        },
        {
            "id": "S05",
            "ok": logo_ok or not _ligado(mapspec, "logo"),
            "mensagem": "Logo IMAP embutido",
        },
        {
            "id": "S06",
            "ok": bool(info_basemap.get("ok")) or not (mapspec.get("basemap") or {}),
            "mensagem": (
                f"Basemap {info_basemap.get('fonte')} aplicado"
                if info_basemap.get("ok")
                else f"Sem imagem de fundo: {info_basemap.get('motivo')}"
            ),
        },
        {
            "id": "S17",
            "ok": (not info_basemap.get("ok"))
            or not info_basemap.get("aviso_resolucao"),
            "mensagem": (
                f"Mosaico com {info_basemap.get('dpi_efetivo')} dpi efetivos no papel"
                if info_basemap.get("ok")
                else "Sem mosaico para medir resolução"
            ),
        },
    ]
    if _deve_sobrepor_tabela(mapspec):
        soft.append(
            {
                "id": "H14",
                "ok": tabela_ok,
                "mensagem": "Tabela PNG sobreposta no PDF"
                if tabela_ok
                else "Tabela pedida mas PNG ausente ou não sobreposto",
            }
        )
        soft.append(
            {
                "id": "S10",
                "ok": tabela_ok,
                "mensagem": "PNG da tabela embutido (resolução do arquivo de origem)",
            }
        )

    soft.append(
        {
            "id": "S23",
            "ok": imovel_livre,
            "mensagem": (
                "Nenhum elemento do layout cobre o imóvel"
                if imovel_livre
                else "Título, rosa, tabela ou quadro cobrem parte do imóvel nesta escala"
            ),
        }
    )
    if _ligado(mapspec, "quadro_resumo", padrao=False):
        soft.append(
            {
                "id": "S24",
                "ok": quadro_ok and all("–" not in linha for linha in (plano_quadro.texto.split("\n") if plano_quadro else [])),
                "mensagem": "Quadro de resumo com as áreas calculadas dos shapes"
                if quadro_ok
                else "Quadro de resumo pedido sem texto",
            }
        )

    relatorio = gerar(motor="nativo", confianca="estrutural", checks_hard=hard, checks_soft=soft)
    json_path = salvar(pasta / f"{nome_base}_validacao.json", relatorio)

    return pdf_path, {
        "pdf": str(pdf_path.relative_to(guard.raiz)),
        "png_pagina": str(png_pagina.relative_to(guard.raiz)),
        "validacao": str(json_path.relative_to(guard.raiz)),
        "validacao_dados": relatorio,
        "tabela_sobreposta": tabela_ok,
        "perfil_pagina": perfil.id,
        "escala": escala,
        "extent": list(extent),
        "grade_passo_segundos": grade.get("passo_segundos"),
        "basemap": {
            "ok": bool(info_basemap.get("ok")),
            # A mesma imagem vira o raster do .mxd (SHP/imagens/), georreferenciada no extent.
            "caminho": (
                str(Path(info_basemap["caminho"]).resolve().relative_to(guard.raiz.resolve()))
                if info_basemap.get("ok") and info_basemap.get("caminho")
                else None
            ),
            "epsg": epsg,
            "camada": info_basemap.get("camada"),
            "fonte": info_basemap.get("fonte"),
            "motivo": info_basemap.get("motivo"),
            "tentativas": info_basemap.get("tentativas"),
        },
        "minimapa": info_minimapa,
    }


def _perfil_do_mapspec(mapspec: dict[str, Any]) -> perfil_pagina.PerfilPagina:
    """Perfil da página: modelo medido primeiro, orientação depois.

    Um mapa da série (`template: serie_*`) tem o layout do **seu** PDF-modelo
    medido em `shared/padrao-imap/anatomia_serie.json`. Só quem não é da série
    cai no perfil genérico por orientação.
    """
    folha = mapspec.get("folha")
    medido = perfil_pagina.por_template(mapspec.get("template"))
    if medido is not None:
        # O modelo da série manda no layout e na orientação; a folha só diz o tamanho.
        return perfil_pagina.escalar_perfil(medido, folha)
    return perfil_pagina.perfil_para(folha or {"orientacao": _orientacao(mapspec)})


def _orientacao(mapspec: dict[str, Any]) -> str:
    """Orientação vem do template (MANIFEST); o MapSpec só desempata."""
    template_id = mapspec.get("template")
    if template_id:
        try:
            from mapasfacil_nucleo.motores.manifesto import obter_template

            tpl = obter_template(str(template_id))
            perfil = perfil_pagina.por_formato(tpl.get("formato_pagina"))
            return perfil.orientacao
        except Exception:  # noqa: BLE001 — template ausente cai no default
            pass
    return str(mapspec.get("orientacao") or "retrato")
