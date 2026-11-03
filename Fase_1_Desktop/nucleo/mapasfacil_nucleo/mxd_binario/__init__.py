"""Submódulo de manipulação e reconstrução binária de documentos MXD (CFBF/OLE2)."""
from __future__ import annotations

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
]
