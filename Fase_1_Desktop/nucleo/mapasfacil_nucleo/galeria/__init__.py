# Galeria — montagem determinística de MapSpec (M4 / F1-15).

from mapasfacil_nucleo.galeria.catalogo import carregar_galeria, obter_modelo
from mapasfacil_nucleo.galeria.estado import avaliar_status
from mapasfacil_nucleo.galeria.montar import montar_mapspec

__all__ = [
    "avaliar_status",
    "carregar_galeria",
    "montar_mapspec",
    "obter_modelo",
]
