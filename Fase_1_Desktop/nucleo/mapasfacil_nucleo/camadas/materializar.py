from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.geo import ogr2ogr as ogr2ogr_util
from mapasfacil_nucleo.motores.manifesto import obter_template

# Nome do dataset em SHP/ que o template preparado espera (F1-04).
NOME_CANONICO_POR_PAPEL: dict[str, str] = {
    "ATP": "ATP",
    "AVN": "AVN",
    "AC": "AREA_CONSOLIDADA",
    "AUAS": "AUAS",
    "APP": "APP",
    "APPD": "APPD",
    "ARL": "ARL",
    "TIPOLOGIA": "TIPOLOGIA_VEGETAL",
    "AIR": "AIR",
    "NASCENTE": "NASCENTE",
}

SUFIXOS_SHAPE = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".xml")


def _resolver_fonte_local(fonte: str, fontes_idx: dict[str, str]) -> str | None:
    if not fonte.startswith("local."):
        return None
    chave = fonte.split(".", 1)[1]
    return fontes_idx.get(chave) or fontes_idx.get(chave.upper())


def _copiar_shapefile(origem: Path, destino_stem: Path) -> None:
    if not origem.exists():
        raise ErroNucleo("NU-120", f"Shapefile de origem ausente: {origem}")
    destino_stem.parent.mkdir(parents=True, exist_ok=True)
    for sufixo in SUFIXOS_SHAPE:
        src = origem.with_suffix(sufixo)
        if src.exists():
            shutil.copy2(src, destino_stem.with_suffix(sufixo))


def materializar_camadas_locais(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
    pasta_shp: str = "SHP",
    reprojetar: bool | None = None,
    ao_materializar: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Copia/reprojeta as camadas locais do MapSpec para `SHP/`.

    `ao_materializar(id_camada, indice, total)` é chamado a cada camada pronta —
    é o que alimenta o `item` de `job.progresso` (F1-01).
    """
    pasta = guard.resolver(pasta_shp, escrita=True)
    pasta.mkdir(parents=True, exist_ok=True)

    epsg_dest: int | None = None
    template_id = mapspec.get("template")
    if isinstance(template_id, str):
        tpl = obter_template(template_id)
        crs = tpl.get("crs_data_frame", mapspec.get("crs", "EPSG:31982"))
        epsg_dest = int(str(crs).replace("EPSG:", ""))

    usar_ogr = reprojetar
    if usar_ogr is None:
        usar_ogr = ogr2ogr_util.disponivel() is not None

    materializados: list[dict[str, str]] = []
    avisos: list[str] = []

    alvos: list[tuple[dict[str, Any], str, str]] = []
    for camada in mapspec.get("camadas", []):
        fonte = camada.get("fonte", "")
        rel = _resolver_fonte_local(fonte, fontes_idx)
        if rel:
            alvos.append((camada, fonte, rel))
    total = len(alvos)

    for indice, (camada, fonte, rel) in enumerate(alvos, start=1):
        origem = guard.resolver(rel)
        id_local = fonte.split(".", 1)[1]
        papel = camada.get("id") or id_local
        nome_dataset = NOME_CANONICO_POR_PAPEL.get(id_local.upper(), id_local.upper())
        destino = pasta / nome_dataset

        try:
            if usar_ogr and epsg_dest is not None:
                ogr2ogr_util.reprojetar_shapefile(origem, destino, epsg_destino=epsg_dest)
            else:
                _copiar_shapefile(origem, destino)
        except ErroNucleo as exc:
            if exc.codigo == "NU-110" and usar_ogr:
                _copiar_shapefile(origem, destino)
                avisos.append(f"{id_local}: ogr2ogr indisponível — cópia sem reprojeção.")
            else:
                avisos.append(exc.mensagem)
                continue

        materializados.append(
            {
                "fonte": fonte,
                "origem": rel,
                "destino": str(destino.with_suffix(".shp").relative_to(guard.raiz)),
                "papel": papel,
            }
        )
        if ao_materializar is not None:
            ao_materializar(papel, indice, total)

    return {
        "pasta": str(pasta.relative_to(guard.raiz)),
        "materializados": materializados,
        "avisos": avisos,
        "reprojetado": bool(usar_ogr and epsg_dest is not None),
        "ogr2ogr": ogr2ogr_util.disponivel(),
    }
