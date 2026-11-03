"""Submódulo de manipulação e reconstrução binária de documentos MXD (CFBF/OLE2)."""
from __future__ import annotations

from .blocos import (
    ArvoreBlocos,
    Bloco,
    extrair_strings_utf16,
    inspecionar_camadas_maps,
    inspecionar_dataframes_maps,
    inspecionar_textos_layout,
)
from .cfbf import (
    AssinaturaInvalidaError,
    CompoundFile,
    CorrupcaoEstruturalError,
    EntradaDiretorio,
    ErroCFBF,
    StreamNaoEncontradaError,
    VersaoNaoSuportadaError,
    ler,
)

__all__ = [
    "CompoundFile",
    "EntradaDiretorio",
    "ErroCFBF",
    "AssinaturaInvalidaError",
    "VersaoNaoSuportadaError",
    "CorrupcaoEstruturalError",
    "StreamNaoEncontradaError",
    "ler",
    "Bloco",
    "ArvoreBlocos",
    "extrair_strings_utf16",
    "inspecionar_textos_layout",
    "inspecionar_camadas_maps",
    "inspecionar_dataframes_maps",
]
