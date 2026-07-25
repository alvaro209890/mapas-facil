from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import numpy as np

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.erros import ErroNucleo

DEFAULT_DPI = 150
DEFAULT_TOLERANCIA_PCT = 0.3
DEFAULT_LIMIAR_RGB = 16


def rasterizar_pdf(caminho: Path, *, dpi: int = DEFAULT_DPI, pagina: int = 0) -> np.ndarray:
    """Rasteriza uma página do PDF em RGB uint8 (anel 1 — sem ArcMap)."""
    if not caminho.is_file():
        raise ErroNucleo("NU-041", f"PDF ausente: {caminho}")

    doc = fitz.open(caminho)
    try:
        if doc.page_count == 0:
            raise ErroNucleo("NU-041", f"PDF sem páginas: {caminho}")
        if pagina < 0 or pagina >= doc.page_count:
            raise ErroNucleo("NU-041", f"Página {pagina} fora do intervalo em {caminho}")

        zoom = dpi / 72.0
        matriz = fitz.Matrix(zoom, zoom)
        pix = doc[pagina].get_pixmap(matrix=matriz, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            arr = arr[:, :, :3]
        return arr
    finally:
        doc.close()


def _recortar_comum(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    return a[:h, :w], b[:h, :w]


def medir_diferenca_raster(
    referencia: np.ndarray,
    gerado: np.ndarray,
    *,
    limiar_rgb: int = DEFAULT_LIMIAR_RGB,
) -> dict[str, Any]:
    """Percentual de pixels que divergem além do limiar por canal."""
    ref, cand = _recortar_comum(referencia, gerado)
    if ref.size == 0:
        return {
            "pixels_total": 0,
            "pixels_diferentes": 0,
            "diferenca_pct": 100.0,
            "dimensoes": {"referencia": list(referencia.shape), "gerado": list(gerado.shape)},
        }

    diff = np.any(np.abs(ref.astype(np.int16) - cand.astype(np.int16)) > limiar_rgb, axis=2)
    total = int(diff.size)
    diferentes = int(diff.sum())
    pct = 100.0 * diferentes / total if total else 100.0
    return {
        "pixels_total": total,
        "pixels_diferentes": diferentes,
        "diferenca_pct": round(pct, 4),
        "dimensoes": {
            "referencia": [int(referencia.shape[0]), int(referencia.shape[1])],
            "gerado": [int(gerado.shape[0]), int(gerado.shape[1])],
            "comparadas": [int(ref.shape[0]), int(ref.shape[1])],
        },
    }


def comparar_pdf(
    gerado: Path,
    referencia: Path,
    *,
    dpi: int = DEFAULT_DPI,
    tolerancia_pct: float = DEFAULT_TOLERANCIA_PCT,
    limiar_rgb: int = DEFAULT_LIMIAR_RGB,
    pagina: int = 0,
) -> dict[str, Any]:
    """Compara dois PDFs por raster (B9). Tolerância padrão: 0,3% de pixels."""
    ref_arr = rasterizar_pdf(referencia, dpi=dpi, pagina=pagina)
    ger_arr = rasterizar_pdf(gerado, dpi=dpi, pagina=pagina)
    medidas = medir_diferenca_raster(ref_arr, ger_arr, limiar_rgb=limiar_rgb)
    diferenca_pct = float(medidas["diferenca_pct"])
    ok = diferenca_pct <= tolerancia_pct

    return {
        "ok": ok,
        "diferenca_pct": diferenca_pct,
        "tolerancia_pct": tolerancia_pct,
        "dpi": dpi,
        "limiar_rgb": limiar_rgb,
        "gerado": str(gerado),
        "referencia": str(referencia),
        **medidas,
    }


def resolver_baseline_template(template_id: str) -> Path | None:
    from mapasfacil_nucleo.motores.manifesto import obter_template

    tpl = obter_template(template_id)
    rel = tpl.get("baseline_pdf")
    if not isinstance(rel, str) or not rel.strip():
        return None
    caminho = raiz_repositorio() / rel
    return caminho if caminho.is_file() else None
