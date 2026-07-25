from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace.papeis import detectar_papel, id_local_de_arquivo
from mapasfacil_nucleo.workspace.recibo_car import eh_recibo_car, parsear
from mapasfacil_nucleo.workspace.shapefile import MetadadosShapefile, inspecionar


def _relativo(raiz: Path, caminho: Path) -> str:
    return caminho.relative_to(raiz).as_posix()


def _montar_fontes(shapefiles: list[dict[str, Any]]) -> list[str]:
    """Stems + aliases de papel curto (AC, TIPOLOGIA…) sem perder camadas distintas."""
    fontes: set[str] = set()
    for item in shapefiles:
        fontes.add(item["id_local"])
        papel = item.get("papel")
        if papel:
            fontes.add(papel)
    return sorted(fontes)


def varrer(raiz: Path, guard: WorkspaceGuard | None = None) -> dict[str, Any]:
    guard = guard or WorkspaceGuard(raiz)
    shapefiles: list[dict[str, Any]] = []
    pdfs: list[dict[str, Any]] = []
    zips: list[dict[str, Any]] = []
    outros: list[dict[str, Any]] = []

    for dirpath, _dirnames, filenames in os.walk(raiz):
        for nome in filenames:
            caminho_abs = Path(dirpath) / nome
            try:
                caminho = guard.resolver(caminho_abs)
            except Exception:
                continue
            rel = _relativo(raiz, caminho)

            if nome.lower().endswith(".shp"):
                meta = inspecionar(caminho)
                papel = detectar_papel(nome)
                shapefiles.append(
                    {
                        "caminho": rel,
                        "papel": papel,
                        "id_local": id_local_de_arquivo(nome),
                        **{k: v for k, v in asdict(meta).items() if k != "caminho"},
                    }
                )
            elif nome.lower().endswith(".pdf"):
                try:
                    recibo = eh_recibo_car(caminho)
                except Exception:
                    recibo = False
                pdfs.append(
                    {
                        "caminho": rel,
                        "recibo_car": recibo,
                    }
                )
            elif nome.lower().endswith(".zip"):
                zips.append({"caminho": rel})
            elif nome.lower().endswith((".mxd", ".png", ".jpg", ".jpeg")):
                outros.append({"caminho": rel, "tipo": Path(nome).suffix.lower()})

    fontes_locais = _montar_fontes(shapefiles)
    recibo_detectado = next((p for p in pdfs if p.get("recibo_car")), None)

    return {
        "raiz": str(raiz),
        "shapefiles": sorted(shapefiles, key=lambda x: x["caminho"]),
        "pdfs": sorted(pdfs, key=lambda x: x["caminho"]),
        "zips": sorted(zips, key=lambda x: x["caminho"]),
        "outros": sorted(outros, key=lambda x: x["caminho"]),
        "fontes_locais": fontes_locais,
        "recibo_car": recibo_detectado["caminho"] if recibo_detectado else None,
    }


def inspecionar_arquivo(guard: WorkspaceGuard, arquivo: str) -> dict[str, Any]:
    caminho = guard.resolver(arquivo)
    if caminho.suffix.lower() == ".shp":
        meta: MetadadosShapefile = inspecionar(caminho)
        return {
            "tipo": "shapefile",
            "papel": detectar_papel(caminho.name),
            **asdict(meta),
        }
    if caminho.suffix.lower() == ".pdf":
        return {
            "tipo": "pdf",
            "recibo_car": eh_recibo_car(caminho),
            "dados": parsear(caminho).para_dict() if eh_recibo_car(caminho) else None,
        }
    return {"tipo": "desconhecido", "caminho": str(caminho)}
