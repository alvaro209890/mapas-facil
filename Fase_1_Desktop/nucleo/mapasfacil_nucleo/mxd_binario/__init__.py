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
from .documento import DocumentoMxd
from .gates import ResultadoGate, verificar_g1, verificar_g2, verificar_g3, verificar_todos
from .pacote import OpcoesPacote, montar_pacote_zip
from .slots import DefinicaoSlot, ErroSlot, ManifestoSlots

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
    "DocumentoMxd",
    "DefinicaoSlot",
    "ManifestoSlots",
    "ErroSlot",
    "ResultadoGate",
    "verificar_g1",
    "verificar_g2",
    "verificar_g3",
    "verificar_todos",
    "OpcoesPacote",
    "montar_pacote_zip",
]
