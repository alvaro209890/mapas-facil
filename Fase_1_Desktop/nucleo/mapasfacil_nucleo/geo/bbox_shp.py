from __future__ import annotations

import struct
from pathlib import Path


def ler_bbox_header_shp(caminho: Path) -> tuple[float, float, float, float]:
    """Lê xmin, ymin, xmax, ymax do cabeçalho do .shp (bytes 36:68, float64 LE)."""
    with caminho.open("rb") as fh:
        fh.seek(36)
        dados = fh.read(32)
    if len(dados) != 32:
        raise ValueError(f"Cabeçalho .shp incompleto: {caminho}")
    return struct.unpack("<4d", dados)
