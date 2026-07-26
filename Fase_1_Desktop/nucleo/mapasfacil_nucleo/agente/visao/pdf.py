# F1-07 caminho 1 — PDF de referência: extrai texto quando dá; sempre rasteriza a
# página 1 (mesma técnica de `validacao/comparar_pdf.py`) — a imagem alimenta as
# medidas determinísticas (`imagem.py`) e, se houver provedor, o modelo de visão.

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from mapasfacil_nucleo.erros import ErroNucleo

DPI_RASTER_PADRAO = 150
LIMIAR_TEXTO_SIGNIFICATIVO = 40  # caracteres — abaixo disso, trata como "sem texto"


def abrir_pdf(caminho: Path) -> fitz.Document:
    if not caminho.is_file():
        raise ErroNucleo("NU-001", f"PDF não encontrado: {caminho.name}")
    try:
        doc = fitz.open(caminho)
    except Exception as exc:  # noqa: BLE001 — PDF corrompido não pode derrubar o núcleo
        raise ErroNucleo("NU-001", f"Não consegui abrir o PDF: {exc}") from exc
    if doc.page_count == 0:
        doc.close()
        raise ErroNucleo("NU-001", f"PDF sem páginas: {caminho.name}")
    return doc


def extrair_texto_pagina1(doc: fitz.Document) -> dict[str, Any]:
    texto = doc[0].get_text() or ""
    texto = texto.strip()
    return {
        "texto": texto,
        "tem_texto": len(texto) >= LIMIAR_TEXTO_SIGNIFICATIVO,
        "num_paginas": doc.page_count,
    }


def rasterizar_pagina1_png(doc: fitz.Document, *, dpi: int = DPI_RASTER_PADRAO) -> bytes:
    zoom = dpi / 72.0
    matriz = fitz.Matrix(zoom, zoom)
    pix = doc[0].get_pixmap(matrix=matriz, alpha=False)
    return pix.tobytes("png")


def analisar_pdf(caminho: Path, *, dpi: int = DPI_RASTER_PADRAO) -> dict[str, Any]:
    """`{texto, tem_texto, num_paginas, png_pagina1}` — nunca lê disco fora do chamado."""
    doc = abrir_pdf(caminho)
    try:
        info = extrair_texto_pagina1(doc)
        info["png_pagina1"] = rasterizar_pagina1_png(doc, dpi=dpi)
        return info
    finally:
        doc.close()
