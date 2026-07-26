# F1-07 caminho 3 — `.zip` de projeto: reusa o leitor do workspace (anti zip-slip,
# `workspace/zip_simcar.py`) e agrupa em inventário tipado. Não extrai nada aqui —
# extração (quando há `.mxd`/PDF a seguir) é responsabilidade de `servico.py`,
# que já passa pelo `fsguard`.

from __future__ import annotations

from pathlib import Path
from typing import Any

from mapasfacil_nucleo.workspace import zip_simcar

EXTENSOES_SHAPE = frozenset({".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx"})


def inventariar(caminho: Path) -> dict[str, Any]:
    bruto = zip_simcar.listar(caminho)

    mxds: list[str] = []
    pdfs: list[str] = []
    stems_shape: dict[str, None] = {}
    outros = 0

    for item in bruto["entradas"]:
        rel = str(item["caminho"])
        sufixo = Path(rel).suffix.lower()
        if sufixo == ".mxd":
            mxds.append(rel)
        elif sufixo == ".pdf":
            pdfs.append(rel)
        elif sufixo in EXTENSOES_SHAPE:
            stem = str(Path(rel).with_suffix(""))
            if stem not in stems_shape:
                stems_shape[stem] = None
        else:
            outros += 1

    return {
        "fonte": "zip_inventario",
        "total_entradas": bruto["total"],
        "mxds": mxds,
        "pdfs": pdfs,
        "shapefiles_stems": list(stems_shape),
        "outros_total": outros,
    }
