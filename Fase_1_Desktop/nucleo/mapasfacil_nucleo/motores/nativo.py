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
        for geom in camada["geometrias"]:
            for poly in _poligonos(geom):
                xs, ys = poly.exterior.xy
                ax.add_patch(
                    PolygonPatch(
                        list(zip(xs, ys)),
                        closed=True,
                        facecolor=face if face else "none",
                        edgecolor=estilo["cor_linha"],
                        linewidth=estilo["largura"],
                        hatch=estilo.get("hachura"),
                        zorder=10,
                    )
                )
                desenhadas += 1
    return desenhadas


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
            valor = str(basemap.get("fonte") or valor)

        pares.append({"rotulo": rotulo, "valor": valor})
    return pares


def _itens_legenda(camadas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for camada in sorted(camadas, key=lambda c: c.get("ordem", 50)):
        rotulo = str(camada.get("legenda") or "").strip()
        if not rotulo or rotulo in vistos:
            continue
        vistos.add(rotulo)
        itens.append({"rotulo": rotulo, "estilo": camada.get("estilo")})
    return itens


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

    perfil = _perfil_do_mapspec(mapspec)
    epsg = _epsg_do_mapspec(mapspec, perfil)

    camadas = _carregar_camadas(mapspec, fontes_idx, guard, epsg)
    extent, escala = _extent(mapspec, camadas, perfil)

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
            )

    if ao_preview is not None:
        ao_preview(_salvar_preview(fig, guard, 1), "aplicando_layout")

    grade = grade_dms.calcular(extent, epsg_projetado=epsg)
    if _ligado(mapspec, "grade"):
        blocos.moldura_e_grade(
            ax, perfil, grade, com_linhas=_ligado(mapspec, "grade_linhas", padrao=False)
        )
    else:
        blocos.moldura_e_grade(ax, perfil, {"x": [], "y": []})

    if _ligado(mapspec, "titulo_caixa"):
        blocos.caixa_titulo(fig, perfil, str(mapspec.get("titulo") or ""))
    if _ligado(mapspec, "norte"):
        blocos.rosa_dos_ventos(fig, perfil)

    metadados = _resolver_metadados(mapspec, epsg=epsg, escala=escala, basemap=info_basemap)
    linhas_meta = 0
    if _ligado(mapspec, "metadados"):
        linhas_meta = blocos.bloco_metadados(
            fig, perfil, metadados, titulo=getattr(perfil, "titulo_metadados", "METADADOS IMAGEM")
        )

    itens_legenda = _itens_legenda(camadas)
    n_legenda = 0
    if _ligado(mapspec, "legenda"):
        n_legenda = blocos.bloco_legenda(fig, perfil, itens_legenda)

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

    logo_ok = False
    if _ligado(mapspec, "logo"):
        logo_ok = blocos.bloco_logo(fig, perfil, raiz_repositorio() / LOGO_PADRAO)

    tabela_ok = False
    if png_tabela is not None and _deve_sobrepor_tabela(mapspec):
        tabela_ok = _sobrepor_png_tabela(fig, perfil, png_tabela)

    if ao_preview is not None:
        ao_preview(_salvar_preview(fig, guard, 2), "aplicando_layout")

    fig.savefig(pdf_path, format="pdf", dpi=DPI_PDF)
    png_pagina = pasta / f"{nome_base}_pagina.png"
    fig.savefig(png_pagina, format="png", dpi=150)
    plt.close(fig)

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
    medido = perfil_pagina.por_template(mapspec.get("template"))
    if medido is not None:
        return medido
    return perfil_pagina.obter(_orientacao(mapspec))


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
