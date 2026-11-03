"""Folhas ISO 216 A (A4–A0) e a geometria de página derivada (W1-01, D31).

Uma função só responde "qual o tamanho da página em mm": `folha_mm(formato, orientacao)`.
Ninguém mais no núcleo, no servidor ou na web carrega essa tabela duplicada — o servidor e o
web **espelham** o JSON de `para_dict()` e o teste `test_folhas_espelho` compara.

Todas as folhas A têm a mesma razão √2: uma folha é a metade da anterior. Por isso o perfil
medido da A4 pode ser escalado por igual para as demais (D31): o fator `k` é
`largura_retrato_mm / 210`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import caminho_shared
from mapasfacil_nucleo.erros import ErroNucleo

# Retrato: (largura, altura) em mm — ISO 216.
FORMATOS: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A2": (420.0, 594.0),
    "A1": (594.0, 841.0),
    "A0": (841.0, 1189.0),
}

ORDEM: tuple[str, ...] = ("A4", "A3", "A2", "A1", "A0")

ORIENTACOES: tuple[str, ...] = ("retrato", "paisagem")

FORMATO_PADRAO = "A4"
ORIENTACAO_PADRAO = "retrato"

# Só existe este valor na v1 (D31). `legivel` é reservado para o futuro.
ESCALA_ELEMENTOS: tuple[str, ...] = ("proporcional",)


def formato_valido(formato: str) -> bool:
    return formato in FORMATOS


def orientacao_valida(orientacao: str) -> bool:
    return orientacao in ORIENTACOES


def folha_mm(formato: str, orientacao: str = ORIENTACAO_PADRAO) -> tuple[float, float]:
    """Largura e altura da página em milímetros.

    Levanta `NU-3xx` (folha) em vez de chutar um default: um mapa no papel errado é
    retrabalho, não aviso.
    """
    if formato not in FORMATOS:
        raise ErroNucleo(
            "NU-301",
            f"Formato de folha desconhecido: {formato!r}. Use um de {', '.join(ORDEM)}.",
            {"formato": formato, "permitidos": list(ORDEM)},
        )
    if orientacao not in ORIENTACOES:
        raise ErroNucleo(
            "NU-302",
            f"Orientação desconhecida: {orientacao!r}. Use 'retrato' ou 'paisagem'.",
            {"orientacao": orientacao, "permitidas": list(ORIENTACOES)},
        )
    largura, altura = FORMATOS[formato]
    return (largura, altura) if orientacao == "retrato" else (altura, largura)


def fator_k(formato: str) -> float:
    """Fator de escala do perfil em relação à A4 retrato (210 mm de largura)."""
    if formato not in FORMATOS:
        raise ErroNucleo(
            "NU-301",
            f"Formato de folha desconhecido: {formato!r}.",
            {"formato": formato, "permitidos": list(ORDEM)},
        )
    return FORMATOS[formato][0] / FORMATOS[FORMATO_PADRAO][0]


def folha_padrao(formato: str = FORMATO_PADRAO, orientacao: str = ORIENTACAO_PADRAO) -> dict[str, Any]:
    """O bloco `folha` do `MapSpec` v3 (D36), já validado."""
    folha_mm(formato, orientacao)  # valida
    return {
        "formato": formato,
        "orientacao": orientacao,
        "escala_elementos": ESCALA_ELEMENTOS[0],
    }


def para_dict() -> dict[str, Any]:
    """Representação estável para a CLI e para o espelho do servidor/web."""
    return {
        "ordem": list(ORDEM),
        "orientacoes": list(ORIENTACOES),
        "formatos": {
            nome: {
                "retrato_mm": list(FORMATOS[nome]),
                "paisagem_mm": [FORMATOS[nome][1], FORMATOS[nome][0]],
                "fator_k": round(fator_k(nome), 6),
            }
            for nome in ORDEM
        },
        "padrao": {"formato": FORMATO_PADRAO, "orientacao": ORIENTACAO_PADRAO},
        "escala_elementos": list(ESCALA_ELEMENTOS),
    }


@lru_cache(maxsize=1)
def _templates_por_id() -> dict[str, dict[str, Any]]:
    caminho: Path = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    return {item["id"]: item for item in dados.get("templates", []) if item.get("id")}


def folha_do_template(template: str) -> dict[str, Any] | None:
    """Folha que o template `.mxd` já usa (`formato_pagina` do MANIFEST).

    É por aqui que o `MapSpec` v2 vira v3 na leitura (D36): o v2 não tinha `folha` e a
    informação sempre existiu no template.
    """
    tpl = _templates_por_id().get(template)
    if not tpl:
        return None
    pagina = tpl.get("formato_pagina") or {}
    formato = pagina.get("papel")
    orientacao = pagina.get("orientacao")
    if formato not in FORMATOS or orientacao not in ORIENTACOES:
        return None
    return folha_padrao(formato, orientacao)
