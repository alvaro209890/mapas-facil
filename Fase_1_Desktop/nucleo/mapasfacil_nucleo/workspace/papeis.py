from __future__ import annotations

import re
import unicodedata

PAPEIS_CANONICOS: dict[str, frozenset[str]] = {
    "ATP": frozenset({"ATP", "AREA_IMOVEL", "PERIMETRO", "AREA_TOTAL", "SIEGEF", "SIGEF"}),
    "AVN": frozenset({"AVN", "VEGETACAO_NATIVA", "VEGETACAO NATIVA"}),
    "AC": frozenset({"AC", "AREA_CONSOLIDADA", "AREA CONSOLIDADA"}),
    "AUAS": frozenset({"AUAS", "AREA_USO_ANTROPIZADO", "DESMATAMENTO"}),
    "APP": frozenset({"APP"}),
    "APPD": frozenset({"APPD"}),
    "ARL": frozenset({"ARL", "ARLD"}),
    "TIPOLOGIA": frozenset({"TIPOLOGIA", "TIPOLOGIA_VEGETAL"}),
}

ALIASES: dict[str, str] = {
    "AREA_CONSOLIDADA": "AC",
    "AREA USO RESTRITO": "AREAS_USO_RESTRITO",
    "VEREDA": "VEREDAS",
}


def _normalizar_nome(nome: str) -> str:
    sem_ext = nome.rsplit(".", 1)[0]
    texto = unicodedata.normalize("NFKD", sem_ext)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.upper().strip()
    texto = re.sub(r"[^A-Z0-9]+", "_", texto)
    return texto.strip("_")


def detectar_papel(nome_arquivo: str) -> str | None:
    base = _normalizar_nome(nome_arquivo)
    if base in ALIASES:
        base = ALIASES[base]
    for papel, nomes in PAPEIS_CANONICOS.items():
        if base in nomes or base.endswith(f"_{papel}") or base.startswith(f"{papel}_"):
            return papel
        if base == papel:
            return papel
    return None
