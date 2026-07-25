from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard

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
) -> dict[str, Any]:
    pasta = guard.resolver(pasta_shp, escrita=True)
    pasta.mkdir(parents=True, exist_ok=True)

    materializados: list[dict[str, str]] = []
    avisos: list[str] = []

    for camada in mapspec.get("camadas", []):
        fonte = camada.get("fonte", "")
        rel = _resolver_fonte_local(fonte, fontes_idx)
        if not rel:
            continue

        origem = guard.resolver(rel)
        id_local = fonte.split(".", 1)[1]
        papel = camada.get("id") or id_local
        nome_dataset = NOME_CANONICO_POR_PAPEL.get(id_local.upper(), id_local.upper())
        destino = pasta / nome_dataset

        try:
            _copiar_shapefile(origem, destino)
        except ErroNucleo as exc:
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

    return {
        "pasta": str(pasta.relative_to(guard.raiz)),
        "materializados": materializados,
        "avisos": avisos,
    }
