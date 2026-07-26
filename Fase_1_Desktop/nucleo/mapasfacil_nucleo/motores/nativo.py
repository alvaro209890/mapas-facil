from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.image import imread
from shapely.ops import transform

from mapasfacil_nucleo.artefatos import PASTA_PREVIEW
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.validacao.relatorio import gerar, salvar
from mapasfacil_nucleo.workspace.shapefile import _abrir_reader, _shapes_para_geometrias, inspecionar

# Posição da tabela no perfil retrato Harmonia (planos/01):
# x 67,1→203,0 mm · y 40,7→60,7 mm a partir da base da página A4 (210×297 mm).
_TABELA_RETRATO = {
    "left": 67.1 / 210.0,
    "bottom": 40.7 / 297.0,
    "width": 135.9 / 210.0,
    "height": 20.0 / 297.0,
}


def _resolver_fonte_local(fonte: str, fontes_idx: dict[str, str]) -> Path | None:
    if not fonte.startswith("local."):
        return None
    chave = fonte.split(".", 1)[1]
    rel = fontes_idx.get(chave)
    return Path(rel) if rel else None


def _plotar_camadas(ax, camadas: list[dict], fontes_idx: dict[str, str], guard: WorkspaceGuard) -> int:
    from pyproj import Transformer

    desenhadas = 0
    # Menor `ordem` desenha por cima (perímetro 10 acima das hachuras 20/30).
    for camada in sorted(camadas, key=lambda c: c.get("ordem", 0), reverse=True):
        fonte = camada.get("fonte", "")
        rel = _resolver_fonte_local(fonte, fontes_idx)
        if not rel:
            continue
        caminho = guard.resolver(rel)
        meta = inspecionar(caminho)
        epsg_origem = meta.crs.get("epsg") or 4674
        epsg_plot = 31982 if epsg_origem in (4326, 4674) else epsg_origem
        transformer = Transformer.from_crs(f"EPSG:{epsg_origem}", f"EPSG:{epsg_plot}", always_xy=True)

        reader, _enc = _abrir_reader(caminho)
        geometrias = _shapes_para_geometrias(reader)
        estilo = camada.get("estilo", "")
        cor = {
            "perimetro_imovel": "#FFD700",
            "avn": "#00AA00",
            "ac": "#FF00FF",
            "auas": "#FF8800",
        }.get(estilo, "#666666")
        for geom in geometrias:
            geom = transform(transformer.transform, geom)
            polys = []
            if geom.geom_type == "Polygon":
                polys = [geom]
            elif geom.geom_type == "MultiPolygon":
                polys = list(geom.geoms)
            else:
                continue
            for poly in polys:
                xs, ys = poly.exterior.xy
                ax.plot(xs, ys, color=cor, linewidth=1.2)
                ax.fill(xs, ys, alpha=0.15, color=cor)
                desenhadas += 1
    return desenhadas


def _deve_sobrepor_tabela(mapspec: dict[str, Any]) -> bool:
    layout = mapspec.get("elementos_layout") or {}
    if "tabela" in layout:
        return bool(layout["tabela"])
    return bool(mapspec.get("tabela"))


def _sobrepor_png_tabela(fig, png_tabela: Path) -> bool:
    """Desenha o PNG da tabela na posição Harmonia (retrato). Retorna True se sobrepôs."""
    if not png_tabela.is_file():
        return False
    ax_tab = fig.add_axes(
        [
            _TABELA_RETRATO["left"],
            _TABELA_RETRATO["bottom"],
            _TABELA_RETRATO["width"],
            _TABELA_RETRATO["height"],
        ]
    )
    img = imread(png_tabela)
    ax_tab.imshow(img, aspect="auto")
    ax_tab.set_xticks([])
    ax_tab.set_yticks([])
    for spine in ax_tab.spines.values():
        spine.set_visible(False)
    return True


DPI_PREVIEW = 72
"""Rasterização intermediária: leve de propósito — é preview, não entrega."""


def _salvar_preview(fig, pasta_saida: Path, guard: WorkspaceGuard, ordem: int) -> str:
    """Grava a rasterização parcial e devolve o caminho **relativo** ao projeto."""
    destino = guard.resolver(
        f"{PASTA_PREVIEW}/parcial_{ordem:02d}.png",
        escrita=True,
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, format="png", dpi=DPI_PREVIEW)
    del pasta_saida
    return str(destino.relative_to(guard.raiz))


def gerar_pdf_minimo(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
    png_tabela: Path | None = None,
    ao_preview: Callable[[str, str], None] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Desenha o mapa e exporta o PDF.

    `ao_preview(caminho_rel, etapa)` é chamado a cada rasterização intermediária —
    é o que alimenta `job.artefato_parcial` do tipo `preview_png` (F1-16 §A5
    fase 2). Sem callback, nada é rasterizado além do PDF: quem chama como
    biblioteca não paga por preview que ninguém vê.
    """
    saida = mapspec.get("saida") or {}
    pasta_nome = saida.get("pasta", "Mapas")
    nome_base = saida.get("nome_base", "mapa")
    pasta = guard.resolver(pasta_nome, escrita=True)
    pdf_path = pasta / f"{nome_base}.pdf"

    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 retrato em polegadas
    ax.set_title(mapspec.get("titulo", "Mapa"))
    desenhadas = _plotar_camadas(ax, mapspec.get("camadas", []), fontes_idx, guard)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linestyle=":", alpha=0.4)

    # Preview 1: camadas desenhadas, antes do layout — a etapa que o usuário
    # está vendo passar na barra quando esta imagem nasce é `aplicando_layout`.
    if ao_preview is not None:
        ao_preview(_salvar_preview(fig, pasta, guard, 1), "aplicando_layout")

    tabela_ok = False
    if png_tabela is not None and _deve_sobrepor_tabela(mapspec):
        # Reserva faixa inferior para a tabela (Harmonia).
        fig.tight_layout(rect=(0.0, 0.18, 1.0, 1.0))
        tabela_ok = _sobrepor_png_tabela(fig, png_tabela)
    else:
        fig.tight_layout()

    # Preview 2: página fechada (com tabela, quando existe) — é o que mais se
    # parece com o PDF que vai sair.
    if ao_preview is not None:
        ao_preview(_salvar_preview(fig, pasta, guard, 2), "aplicando_layout")

    fig.savefig(pdf_path, format="pdf", dpi=150)
    plt.close(fig)

    hard = [
        {"id": "H09", "ok": desenhadas > 0, "mensagem": "Mapa contém geometrias desenhadas"},
        {"id": "H02", "ok": True, "mensagem": "PDF gerado em A4 retrato"},
    ]
    soft = []
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
        "validacao": str(json_path.relative_to(guard.raiz)),
        "validacao_dados": relatorio,
        "tabela_sobreposta": tabela_ok,
    }
