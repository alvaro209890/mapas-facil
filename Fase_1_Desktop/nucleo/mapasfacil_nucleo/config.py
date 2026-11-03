from __future__ import annotations

import os
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


# --- modo servidor (Fase 3, W1-02) -----------------------------------------
#
# O único lugar do núcleo que lê `MAPASFACIL_MODO`. Em modo servidor o núcleo roda
# como processo filho do backend web: sem keyring, sem conta local, sem watcher,
# com vagas de geração compartilhadas por `flock` e saída por versão (D23, W-04).
MODO_SERVIDOR = "servidor"
_MODOS = frozenset({"desktop", MODO_SERVIDOR})


def modo() -> str:
    """`"desktop"` (padrão) ou `"servidor"`."""
    bruto = (os.environ.get("MAPASFACIL_MODO") or "desktop").strip().lower()
    return bruto if bruto in _MODOS else "desktop"


def modo_servidor() -> bool:
    return modo() == MODO_SERVIDOR


def pasta_saida_versao(versao: int) -> str:
    """Pasta de saída de uma versão no modo servidor: `Mapas/v003` (W1-08).

    No desktop a saída continua sendo `Mapas/` com o sufixo `_vN` no nome do arquivo;
    no servidor cada versão tem pasta própria, que é o que a web lista e baixa.
    """
    numero = max(int(versao), 1)
    return f"Mapas/v{numero:03d}"


def pasta_saida(*, versao: int | None = None) -> str:
    """`Mapas/vNNN` em modo servidor (quando há versão), `Mapas` no desktop."""
    if modo_servidor() and versao:
        return pasta_saida_versao(versao)
    return "Mapas"


ENV_VERSAO_SAIDA = "MAPASFACIL_VERSAO_SAIDA"


def versao_saida() -> int:
    """Versão corrente do projeto quando o servidor dispara a geração (padrão 1)."""
    bruto = (os.environ.get(ENV_VERSAO_SAIDA) or "").strip()
    if not bruto:
        return 1
    try:
        return max(int(bruto), 1)
    except ValueError:
        return 1


def raiz_repositorio() -> Path:
    """Raiz do monorepo (Mapas_Facil/).

    Empacotado (PyInstaller), `__file__` aponta para dentro do bundle e a
    contagem de `parents` deixa de valer. A âncora passa a ser `sys._MEIPASS`,
    a pasta onde o PyInstaller põe os `datas` (`_internal/` no modo onedir).
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        return Path(base) if base else Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def caminho_shared(*partes: str) -> Path:
    return raiz_repositorio().joinpath("shared", *partes)
