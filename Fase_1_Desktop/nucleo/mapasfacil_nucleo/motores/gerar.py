from __future__ import annotations

from pathlib import Path
from typing import Any

from pyproj import Transformer

from mapasfacil_nucleo.camadas.materializar import materializar_camadas_locais
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.geo.bbox_shp import ler_bbox_header_shp
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.motores.manifesto import obter_template
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.motores.patch_mxd import gerar_mxd_t2
from mapasfacil_nucleo.workspace.shapefile import inspecionar


def _resolver_fonte_local(fonte: str, fontes_idx: dict[str, str]) -> str | None:
    if not fonte.startswith("local."):
        return None
    chave = fonte.split(".", 1)[1]
    return fontes_idx.get(chave) or fontes_idx.get(chave.upper())


def _resolver_bbox_utm(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
) -> tuple[float, float, float, float] | None:
    extent = mapspec.get("extent")
    if isinstance(extent, dict):
        return (
            float(extent["xmin"]),
            float(extent["ymin"]),
            float(extent["xmax"]),
            float(extent["ymax"]),
        )

    geometria = (mapspec.get("imovel") or {}).get("geometria", "local.ATP")
    rel = _resolver_fonte_local(geometria, fontes_idx)
    if not rel:
        for camada in mapspec.get("camadas", []):
            rel = _resolver_fonte_local(camada.get("fonte", ""), fontes_idx)
            if rel:
                break
    if not rel:
        return None

    caminho = guard.resolver(rel)
    meta = inspecionar(caminho)
    bbox = meta.bbox
    xmin, ymin, xmax, ymax = bbox["xmin"], bbox["ymin"], bbox["xmax"], bbox["ymax"]

    template_id = mapspec.get("template")
    if not template_id:
        return xmin, ymin, xmax, ymax

    tpl = obter_template(str(template_id))
    crs_dest = tpl.get("crs_data_frame", mapspec.get("crs", "EPSG:31982"))
    epsg_dest = int(str(crs_dest).replace("EPSG:", ""))
    epsg_orig = meta.crs.get("epsg") or 31982
    if epsg_orig == epsg_dest:
        return xmin, ymin, xmax, ymax

    transformer = Transformer.from_crs(
        f"EPSG:{epsg_orig}",
        f"EPSG:{epsg_dest}",
        always_xy=True,
    )
    xs = [xmin, xmin, xmax, xmax]
    ys = [ymin, ymax, ymin, ymax]
    tx, ty = transformer.transform(xs, ys)
    return min(tx), min(ty), max(tx), max(ty)


def gerar_mapa(
    mapspec: dict[str, Any],
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
) -> dict[str, Any]:
    resultado_val = validar(mapspec, fontes_locais=frozenset(fontes_idx))
    if not resultado_val["valido"]:
        primeiro = resultado_val["erros"][0]
        raise ErroNucleo(primeiro["codigo"], primeiro["mensagem"], {"erros": resultado_val["erros"]})

    saidas = mapspec.get("saidas") or ["pdf"]
    saida_cfg = mapspec.get("saida") or {}
    pasta_shp = saida_cfg.get("materializar_camadas_em", "SHP")

    artefatos: dict[str, Any] = {}
    avisos: list[str] = []
    resultado: dict[str, Any] = {"artefatos": artefatos, "avisos": avisos}

    precisa_shp = bool(saida_cfg.get("materializar_camadas_em")) or "mxd" in saidas
    if precisa_shp:
        materializacao = materializar_camadas_locais(
            mapspec,
            guard=guard,
            fontes_idx=fontes_idx,
            pasta_shp=pasta_shp,
        )
        artefatos["materializacao"] = materializacao
        avisos.extend(materializacao.get("avisos", []))

    if "mxd" in saidas:
        if not mapspec.get("template"):
            raise ErroNucleo("NU-205", "MapSpec pede .mxd mas não informa template.")
        bbox = _resolver_bbox_utm(mapspec, guard=guard, fontes_idx=fontes_idx)
        escala = mapspec.get("escala")
        mxd_info = gerar_mxd_t2(
            mapspec,
            guard=guard,
            bbox=bbox,
            escala=float(escala) if escala is not None else None,
        )
        artefatos["mxd"] = mxd_info
        resultado["mxd"] = mxd_info["mxd"]
        avisos.extend(mxd_info.get("patch", {}).get("avisos", []))

    if "pdf" in saidas:
        _, pdf_artefatos = gerar_pdf_minimo(mapspec, guard=guard, fontes_idx=fontes_idx)
        artefatos.update(pdf_artefatos)
        resultado["pdf"] = pdf_artefatos["pdf"]

    return resultado
