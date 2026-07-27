from __future__ import annotations

import sys
from pathlib import Path

from mapasfacil_nucleo import __version__

PROTOCOLO_VERSAO = 1
NUCLEO_VERSAO = __version__

# Escalas "bonitas" — planos/01-padrao-imap-harmonia.md
ESCALAS_PERMITIDAS: frozenset[int] = frozenset(
    {
        5_000,
        7_500,
        10_000,
        12_500,
        15_000,
        20_000,
        22_000,
        25_000,
        30_000,
        40_000,
        50_000,
        60_000,
        75_000,
        90_000,
        100_000,
        105_000,
        125_000,
        150_000,
        200_000,
        250_000,
    }
)

PASTAS_ESCRITA = frozenset({"Mapas", "MXD", "SHP", "_extraido"})

NOMES_RESERVADOS_WINDOWS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

CARACTERES_INVALIDOS_WINDOWS = frozenset('<>:"|?*')

LIMITE_CAMINHO_WINDOWS = 260
LIMITE_COMPONENTE = 255


def empacotado() -> bool:
    """True quando o sidecar roda como binário PyInstaller (F1-11 onedir)."""
    return bool(getattr(sys, "frozen", False))


def raiz_repositorio() -> Path:
    """Raiz dos dados do produto.

    Em desenvolvimento: raiz do monorepo (`shared/`, `Referencias_IMAP/`, …).
    Empacotado (PyInstaller onedir): pasta do `nucleo.exe`, onde mora `shared/`.
    """
    if empacotado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def caminho_shared(*partes: str) -> Path:
    return raiz_repositorio().joinpath("shared", *partes)
