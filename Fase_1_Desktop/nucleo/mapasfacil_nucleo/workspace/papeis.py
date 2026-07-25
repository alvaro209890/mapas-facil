from __future__ import annotations

import re
import unicodedata

# Papéis reconhecidos no índice do workspace.
# Nomes calibrados contra Referencias_IMAP/Mapas/03/Arquivo Processado (11)/ (SIMCAR)
# e contra o acervo Harmonia (Mapas/01 + DOC MXD).
PAPEIS_CANONICOS: dict[str, frozenset[str]] = {
    "ATP": frozenset(
        {"ATP", "AREA_IMOVEL", "PERIMETRO", "AREA_TOTAL", "SIEGEF", "SIGEF", "FAZENDA_HARMONIA"}
    ),
    "AVN": frozenset({"AVN", "VEGETACAO_NATIVA", "VEGETACAO NATIVA"}),
    "AC": frozenset({"AC", "AREA_CONSOLIDADA", "AREA CONSOLIDADA"}),
    "AUAS": frozenset({"AUAS", "AREA_USO_ANTROPIZADO", "DESMATAMENTO"}),
    "APP": frozenset({"APP"}),
    "APPD": frozenset({"APPD"}),
    "APPRL": frozenset({"APPRL"}),
    "ARL": frozenset(
        {
            "ARL",
            "ARLD",
            "ARLREM",
            "ARL_CERRADO_PRESERVADA",
            "ARL_CERRADO_RECOMPOR",
            "ARL_FLORESTA_PRESERVADA",
            "ARL_FLORESTA_RECOMPOR",
        }
    ),
    "TIPOLOGIA": frozenset({"TIPOLOGIA", "TIPOLOGIA_VEGETAL"}),
    "AIR": frozenset({"AIR", "ALERTA", "ALERTAS"}),
    "NASCENTE": frozenset({"NASCENTE", "NASCENTES"}),
    "VEREDA": frozenset({"VEREDA", "VEREDAS"}),
    "AURD": frozenset({"AURD"}),
    "AREA_USO_RESTRITO": frozenset({"AREA_USO_RESTRITO", "AREAS_USO_RESTRITO"}),
    "AREA_UMIDA": frozenset({"AREA_UMIDA", "AREAS_UMIDAS"}),
    "HIDRO_POLIGONO": frozenset(
        {
            "RIO_ATE_10",
            "RIO_10_A_50",
            "RIO_50_A_200",
            "RIO_200_A_600",
            "RIO_ACIMA_600",
            "LAGOA_NATURAL",
            "RESERVATORIO_ARTIFICIAL",
            "MANGUEZAL",
            "RESTINGA",
        }
    ),
    "HIDRO_LINHA": frozenset({"RIO_LINHA"}),
    "AREA_ABRANGENCIA": frozenset({"AREA_ABRANGENCIA"}),
}

# Normalização de aliases soltos → nome canônico de papel (após _normalizar_nome)
ALIASES: dict[str, str] = {
    "AREA_CONSOLIDADA": "AC",
    "AREA_USO_RESTRITO": "AREA_USO_RESTRITO",
    "AREAS_USO_RESTRITO": "AREA_USO_RESTRITO",
    "VEREDAS": "VEREDA",
    "TIPOLOGIA_VEGETAL": "TIPOLOGIA",
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
        if base in nomes or base == papel:
            return papel
        if base.endswith(f"_{papel}") or base.startswith(f"{papel}_"):
            return papel
    return None
