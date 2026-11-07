"""Pacote de layouts declarativos e versionados (LayoutSpec) para Mapas Fácil."""

from .conversor import de_perfil, perfil_do_layout
from .loader import carregar, listar_layouts, obter_layout
from .medir import medir
from .modelo import CaixaMm, DimensoesMm, FolhaPadrao, LayoutSpec, Tipografia
from .validar import validar

__all__ = [
    "CaixaMm",
    "DimensoesMm",
    "FolhaPadrao",
    "LayoutSpec",
    "Tipografia",
    "carregar",
    "de_perfil",
    "listar_layouts",
    "medir",
    "obter_layout",
    "perfil_do_layout",
    "validar",
]
