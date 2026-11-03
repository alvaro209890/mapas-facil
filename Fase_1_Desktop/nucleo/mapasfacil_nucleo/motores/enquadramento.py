"""Enquadramento: qual folha e qual escala servem para este imóvel (W-10, núcleo).

O que faz: dado o retângulo do imóvel e uma folha (A4–A0, retrato ou paisagem), calcula a
**menor escala redonda** em que o imóvel cabe inteiro dentro do quadro do mapa, com margem,
e o **aproveitamento** (quanto do quadro o imóvel ocupa).

Regras que vêm da Análise PH (planos W-00 e W-10):

- faixa útil = o quadro do mapa, não a folha inteira;
- margem de 8 % em volta (respiro para o perímetro e o rótulo das classes);
- escala **redonda para cima** — a lista de escalas permitidas é a da casa
  (`config.ESCALAS_PERMITIDAS`), nunca uma escala inventada;
- a mesma escala vale para a série inteira: quem chama passa o mesmo retângulo.

O que **não** faz (é do W11 completo): composição do quadro, escolha automática de qual
camada manda no zoom, e a tabela por classe. Aqui só se responde "cabe em qual folha, em
que escala, aproveitando quanto".
"""

from __future__ import annotations

from typing import Any, Iterable

from mapasfacil_nucleo.config import ESCALAS_PERMITIDAS
from mapasfacil_nucleo.motores.folhas import ORDEM, folha_mm

# Respiro em volta do imóvel (fração de cada lado).
MARGEM = 0.08

# Área útil do quadro de mapa como fração da folha. Vem do perfil A4 da casa
# (`perfil_pagina`): o mapa não ocupa a folha inteira porque há moldura, legenda e rodapé.
_FRACAO_UTIL = (0.86, 0.78)

ORIENTACOES = ("retrato", "paisagem")


def quadro_util_mm(formato: str, orientacao: str = "paisagem") -> tuple[float, float]:
    """Largura e altura, em mm, do quadro de mapa dentro da folha."""
    largura, altura = folha_mm(formato, orientacao)
    return largura * _FRACAO_UTIL[0], altura * _FRACAO_UTIL[1]


def _extensao_m(bbox: dict[str, Any], margem: float = MARGEM) -> tuple[float, float]:
    largura = abs(float(bbox["xmax"]) - float(bbox["xmin"]))
    altura = abs(float(bbox["ymax"]) - float(bbox["ymin"]))
    if largura <= 0 or altura <= 0:
        return (max(largura, 1.0), max(altura, 1.0))
    return largura * (1 + 2 * margem), altura * (1 + 2 * margem)


def escala_minima(bbox: dict[str, Any], formato: str, orientacao: str = "paisagem") -> float:
    """Escala (contínua) em que o imóvel cabe inteiro no quadro, com margem."""
    largura_m, altura_m = _extensao_m(bbox)
    largura_mm, altura_mm = quadro_util_mm(formato, orientacao)
    # metros de terreno por mm de papel → escala
    return max(largura_m / (largura_mm / 1000.0), altura_m / (altura_mm / 1000.0))


def escala_redonda(escala: float, *, permitidas: Iterable[int] | None = None) -> int:
    """Primeira escala da casa que é maior ou igual à pedida (arredonda para cima)."""
    banco = sorted(permitidas or ESCALAS_PERMITIDAS)
    for candidata in banco:
        if candidata >= escala:
            return candidata
    return banco[-1]


def aproveitamento(bbox: dict[str, Any], formato: str, orientacao: str, escala: int) -> float:
    """Quanto do quadro o imóvel ocupa, em % (0–100)."""
    largura_m = abs(float(bbox["xmax"]) - float(bbox["xmin"]))
    altura_m = abs(float(bbox["ymax"]) - float(bbox["ymin"]))
    largura_mm, altura_mm = quadro_util_mm(formato, orientacao)
    util_m2 = (largura_mm / 1000.0 * escala) * (altura_mm / 1000.0 * escala)
    if util_m2 <= 0:
        return 0.0
    return round(100.0 * (largura_m * altura_m) / util_m2, 1)


def para_dict(
    bbox: dict[str, Any],
    formato: str,
    orientacao: str = "paisagem",
) -> dict[str, Any]:
    """Uma linha da tabela de sugestão: folha, orientação, escala redonda e aproveitamento."""
    minima = escala_minima(bbox, formato, orientacao)
    escala = escala_redonda(minima)
    return {
        "folha": formato,
        "orientacao": orientacao,
        "escala": escala,
        "escala_texto": f"1:{escala:,}".replace(",", "."),
        "aproveitamento_pct": aproveitamento(bbox, formato, orientacao, escala),
    }


def sugerir(
    bbox: dict[str, Any],
    *,
    formatos: Iterable[str] = ORDEM,
) -> list[dict[str, Any]]:
    """Tabela folha × orientação, da folha com **mais** aproveitamento para a com menos.

    Aproveitamento alto = mapa mais detalhado na mesma informação. Empate desfeito pela
    folha menor (que gasta menos papel e cabe na impressora do escritório).
    """
    linhas = [
        para_dict(bbox, formato, orientacao)
        for formato in formatos
        for orientacao in ORIENTACOES
    ]
    linhas.sort(key=lambda l: (-l["aproveitamento_pct"], ORDEM.index(l["folha"]), l["orientacao"]))
    return linhas


def melhor(bbox: dict[str, Any], *, formatos: Iterable[str] = ORDEM) -> dict[str, Any] | None:
    linhas = sugerir(bbox, formatos=formatos)
    return linhas[0] if linhas else None
