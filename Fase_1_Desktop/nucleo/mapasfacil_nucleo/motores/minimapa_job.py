"""Monta o payload T1 (ArcPy) a partir do MapSpec — municipio, graficos, IBGE."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from pyproj import Transformer

from mapasfacil_nucleo.camadas import ibge as ibge_mod
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores import arcpy_ponte
from mapasfacil_nucleo.motores import minimapa as minimapa_mod
from mapasfacil_nucleo.motores.manifesto import obter_template
from mapasfacil_nucleo.workspace.shapefile import inspecionar

# Stems canônicos → nomes que o template Dinâmica ainda pode exigir (acervo).
_HOMONIMOS_SHAPE: dict[str, tuple[str, ...]] = {
    "ATP": ("CAR_ATP", "Fazenda_Harmonia", "Fazenda_Santa_Clara"),
    "AREA_CONSOLIDADA": ("AC", "AREA_CONSOLIDADA"),
    "AVN": ("AVN",),
    "AUAS": ("AUAS",),
}

_SUFIXOS_SHAPE = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx")


def _garantir_homonimos_shp(pasta_shp: Path) -> None:
    """Copia ATP.shp → CAR_ATP.shp etc. para findAndReplaceWorkspacePaths resolver."""
    for canonico, aliases in _HOMONIMOS_SHAPE.items():
        origem = pasta_shp / f"{canonico}.shp"
        if not origem.is_file():
            continue
        for alias in aliases:
            if alias == canonico:
                continue
            destino = pasta_shp / f"{alias}.shp"
            if destino.is_file():
                continue
            for sufixo in _SUFIXOS_SHAPE:
                src = origem.with_suffix(sufixo)
                if src.is_file():
                    shutil.copy2(src, pasta_shp / f"{alias}{sufixo}")


def _centroide_wgs84(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
) -> tuple[float, float] | None:
    """Lon/lat do imóvel (WGS84) a partir do ATP/SHP ou None."""
    geometria = (mapspec.get("imovel") or {}).get("geometria", "local.ATP")
    if not isinstance(geometria, str) or not geometria.startswith("local."):
        return None
    chave = geometria.split(".", 1)[1]
    rel = fontes_idx.get(chave) or fontes_idx.get(chave.upper())
    if not rel:
        # tenta SHP materializado
        for cand in ("SHP/ATP.shp", "dados/ATP.shp"):
            try:
                caminho = guard.resolver(cand)
                if caminho.is_file():
                    rel = cand
                    break
            except Exception:
                continue
    if not rel:
        return None
    caminho = guard.resolver(rel)
    meta = inspecionar(caminho)
    bbox = meta.bbox
    cx = (bbox["xmin"] + bbox["xmax"]) / 2.0
    cy = (bbox["ymin"] + bbox["ymax"]) / 2.0
    epsg = meta.crs.get("epsg") or 31982
    if epsg == 4326:
        return cx, cy
    to_wgs = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = to_wgs.transform(cx, cy)
    return float(lon), float(lat)


def montar_contexto_minimapa(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
) -> dict[str, Any]:
    """Dados prontos para o job ArcPy (queries + graficos + extent)."""
    imovel = mapspec.get("imovel") or {}
    mun = imovel.get("municipio") or {}
    nome = mun.get("nome") or ""
    uf_sigla = mun.get("uf") or "MT"
    ibge_cod = mun.get("ibge")
    resolvido = ibge_mod.resolver_municipio(nome=nome, ibge=ibge_cod)
    if resolvido:
        nome = resolvido["nome"]
        uf_sigla = resolvido.get("sigla_uf") or uf_sigla
        ibge_cod = resolvido.get("cod_ibge") or ibge_cod
    uf_extenso = ibge_mod.uf_sigla_para_nome(uf_sigla)
    extent = ibge_mod.extent_municipio(nome=nome, ibge=ibge_cod)
    graficos: dict[str, Any] = {}
    centro = _centroide_wgs84(mapspec, guard=guard, fontes_idx=fontes_idx)
    if extent and centro:
        calc = minimapa_mod.graficos_para_centroide(
            lon=centro[0],
            lat=centro[1],
            extent_minimapa_wgs84=extent,
        )
        graficos = calc.get("graficos_arcpy_cm") or {}
    return {
        "municipio": nome,
        "uf_sigla": uf_sigla,
        "uf_extenso": uf_extenso,
        "ibge": ibge_cod,
        "extent_minimapa_wgs84": list(extent) if extent else None,
        "graficos": graficos,
        "textos": {
            "ROTULO_MUNICIPIO": nome,
            "UF_SELO": str(uf_sigla).upper(),
        },
        "centroide_wgs84": list(centro) if centro else None,
        "pasta_ibge": str(ibge_mod.pasta_shapefile_repo()),
    }


def tentar_gerar_mxd_arcpy(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
    bbox: tuple[float, float, float, float] | None,
    escala: float | None,
    pasta_shp: str,
) -> dict[str, Any] | None:
    """Se ArcMap estiver disponível, gera MXD via T1 com minimapa. Senão None."""
    python_arc = arcpy_ponte._python_arcmap_padrao()
    if not python_arc:
        return None

    elementos = mapspec.get("elementos_layout") or {}
    quer_minimapa = bool(elementos.get("minimapa", True))
    template_id = mapspec.get("template")
    if not template_id:
        return None
    tpl = obter_template(str(template_id))
    from mapasfacil_nucleo.motores.manifesto import resolver_caminho_preparado

    template_path = resolver_caminho_preparado(tpl)
    if not template_path.is_file():
        return None

    saida_cfg = mapspec.get("saida") or {}
    pasta_saida = guard.resolver(saida_cfg.get("pasta", "Mapas"), escrita=True)
    nome_base = saida_cfg.get("nome_base", "mapa")
    saida_mxd = pasta_saida / f"{nome_base}.mxd"
    pasta_saida_shp = guard.resolver(pasta_shp, escrita=True)

    # Homônimos que o template ainda espera (técnica F1-04) — sem replaceDataSource.
    _garantir_homonimos_shp(pasta_saida_shp)

    ctx = montar_contexto_minimapa(mapspec, guard=guard, fontes_idx=fontes_idx)
    if not quer_minimapa:
        ctx["graficos"] = {}

    # extent minimapa no CRS do DF (3857) se possível
    extent_job = None
    if ctx.get("extent_minimapa_wgs84") and ctx.get("centroide_wgs84"):
        calc = minimapa_mod.graficos_para_centroide(
            lon=ctx["centroide_wgs84"][0],
            lat=ctx["centroide_wgs84"][1],
            extent_minimapa_wgs84=tuple(ctx["extent_minimapa_wgs84"]),
        )
        extent_job = list(calc.get("extent_minimapa_df") or [])
        if not ctx.get("graficos"):
            ctx["graficos"] = calc.get("graficos_arcpy_cm") or {}

    tmp = Path(tempfile.mkdtemp(prefix="mf_arcpy_"))
    bbox_list = list(bbox) if bbox else [0.0, 0.0, 1.0, 1.0]
    # PDF ArcMap ao lado do nativo (critério M2 §1.5): *_arcmap.pdf
    saidas_job = ["mxd"]
    saida_pdf_arc = None
    if "pdf" in (mapspec.get("saidas") or []):
        saidas_job.append("pdf")
        saida_pdf_arc = str(pasta_saida / f"{nome_base}_arcmap.pdf")

    imovel = mapspec.get("imovel") or {}
    textos = dict(ctx.get("textos") or {})
    titulo = mapspec.get("titulo")
    if titulo:
        textos.setdefault("TITULO", str(titulo))
    if imovel.get("nome"):
        textos.setdefault("ROTULO_IMOVEL", str(imovel["nome"]))

    payload = arcpy_ponte.montar_payload(
        template=str(template_path),
        tmp_dir=str(tmp),
        pasta_template_shp=str(template_path.parent / "SHP"),
        pasta_saida_shp=str(pasta_saida_shp),
        bbox_no_crs_do_data_frame=bbox_list,
        escala=float(escala or 60000),
        municipio=ctx["municipio"],
        uf_extenso=ctx["uf_extenso"],
        textos=textos,
        graficos=ctx["graficos"],
        saidas=saidas_job,
        saida_mxd=str(saida_mxd),
        saida_pdf=saida_pdf_arc,
        pasta_ibge=ctx["pasta_ibge"] if Path(ctx["pasta_ibge"]).is_dir() else None,
        extent_minimapa=extent_job,
    )
    resultado = arcpy_ponte.executar(payload, python_exe=python_arc)
    rel_mxd = str(saida_mxd.relative_to(guard.raiz))
    info: dict[str, Any] = {
        "mxd": rel_mxd,
        "motor": "arcpy",
        "confianca": "cartografica" if ctx.get("graficos") else "estrutural",
        "tier": "T1",
        "minimapa": {
            "municipio": ctx["municipio"],
            "uf": ctx["uf_sigla"],
            "graficos": bool(ctx.get("graficos")),
            "pasta_ibge": ctx["pasta_ibge"],
        },
        "relatorio_arcpy": resultado.get("relatorio"),
        "patch": {"avisos": []},
    }
    if saida_pdf_arc and Path(saida_pdf_arc).is_file():
        info["pdf_arcmap"] = str(Path(saida_pdf_arc).relative_to(guard.raiz))
    return info
