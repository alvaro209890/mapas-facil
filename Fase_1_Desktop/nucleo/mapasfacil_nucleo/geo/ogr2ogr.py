from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from mapasfacil_nucleo.erros import ErroNucleo


def disponivel() -> str | None:
    return shutil.which("ogr2ogr")


def reprojetar_shapefile(
    origem: Path,
    destino_stem: Path,
    *,
    epsg_destino: int,
) -> None:
    ogr = disponivel()
    if not ogr:
        raise ErroNucleo(
            "NU-110",
            "ogr2ogr não encontrado — cópia sem reprojeção.",
        )

    destino_stem.parent.mkdir(parents=True, exist_ok=True)
    saida = destino_stem.with_suffix(".shp")
    cmd = [
        ogr,
        "-f",
        "ESRI Shapefile",
        str(saida),
        str(origem.with_suffix(".shp")),
        "-t_srs",
        f"EPSG:{epsg_destino}",
        "-overwrite",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise ErroNucleo("NU-110", "Timeout do ogr2ogr.") from exc

    if proc.returncode != 0:
        raise ErroNucleo(
            "NU-110",
            "ogr2ogr falhou.",
            {"stderr": (proc.stderr or "")[-500:]},
        )
