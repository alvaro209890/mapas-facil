# Persistência local de conversas (M6 / F1-17). Sem rede — D20.

from mapasfacil_nucleo.conversas.banco import SCHEMA_VERSAO_ATUAL, diretorio_chats
from mapasfacil_nucleo.conversas.fingerprint import fingerprint_workspace
from mapasfacil_nucleo.conversas.redator import redigir
from mapasfacil_nucleo.conversas.titulo import TITULO_PADRAO

__all__ = [
    "SCHEMA_VERSAO_ATUAL",
    "TITULO_PADRAO",
    "diretorio_chats",
    "fingerprint_workspace",
    "redigir",
]
