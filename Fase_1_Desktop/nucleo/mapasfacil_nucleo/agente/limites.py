"""Orçamento de contexto do agente — constantes vinculantes (G2 / F1-06).

Teto e códigos de erro vivem aqui. O pipeline compactar → resumir → recusar
(`IA-040`) fica em `contexto.py`; este módulo só exporta números e helpers puros
(sem I/O, sem rede, sem `raise ErroNucleo`).

Estimativa de tokens no anel 1: `ceil(len / 4)` sobre texto UTF-8 — heurística
determinística, sem tiktoken. Não é a contagem do provedor; serve para gates
internos de compressão e truncamento.
"""

from __future__ import annotations

import json
import math
from typing import Any

# --------------------------------------------------------------------------- tetos (F1-06)

ENTRADA_MAX_POR_TURNO = 60_000
SAIDA_MAX_TOKENS = 8_000
RODADAS_TOOL_MAX_POR_TURNO = 12
TOKENS_CONVERSA_MAX = 400_000
RESULTADO_TOOL_MAX = 2_000
MEMORIA_TRABALHO_MAX = 1_200
COMPACT_SUMMARY_MAX = 800
TURNOS_VERBATIM = 8
SYSTEM_PROMPT_MAX = 2_500
COMPACT_SUMMARY_REGENERAR_CADA = 6
MAPSPEC_DIFF_MAX = 2_000
INDICE_WORKSPACE_MAX_ARQUIVOS = 80

# --------------------------------------------------------------------------- códigos IA-*

CODIGO_SEM_CHAVE = "IA-001"
CODIGO_PROVEDOR_INDISPONIVEL = "IA-010"
CODIGO_TOOL_INEXISTENTE = "IA-020"
CODIGO_LIMITE_RODADAS = "IA-030"
CODIGO_CONTEXTO_EXCEDIDO = "IA-040"
CODIGO_TETO_CONVERSA = "IA-041"
CODIGO_RESPOSTA_TRUNCADA = "IA-050"

# --------------------------------------------------------------------------- helpers


def estimar_tokens(texto: str) -> int:
    """Heurística anel 1: ~1 token por 4 caracteres (arredonda para cima)."""
    if not texto:
        return 0
    return math.ceil(len(texto) / 4)


def estimar_tokens_json(obj: Any) -> int:
    """Tokens estimados do JSON serializado de forma estável (`sort_keys`)."""
    serializado = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return estimar_tokens(serializado)


def cabe_em(tokens: int, teto: int) -> bool:
    return tokens <= teto


def excede_entrada_turno(tokens: int) -> bool:
    return tokens > ENTRADA_MAX_POR_TURNO


def excede_conversa(tokens_acumulados: int) -> bool:
    return tokens_acumulados > TOKENS_CONVERSA_MAX


def rodada_tool_permitida(rodada: int) -> bool:
    """Rodadas 1..12 inclusive são permitidas; a 13ª (e acima) não."""
    return 1 <= rodada <= RODADAS_TOOL_MAX_POR_TURNO


def deve_regenerar_compact_summary(turnos_desde_ultimo: int) -> bool:
    """Regenera a cada `COMPACT_SUMMARY_REGENERAR_CADA` turnos novos (≥ 6)."""
    return turnos_desde_ultimo >= COMPACT_SUMMARY_REGENERAR_CADA


def mapspec_diff_cabe(tokens_diff: int) -> bool:
    """Diff ≤ 2000 tokens vai no payload; acima manda o MapSpec completo de novo."""
    return tokens_diff <= MAPSPEC_DIFF_MAX


def indice_precisa_resumo(n_arquivos: int) -> bool:
    return n_arquivos > INDICE_WORKSPACE_MAX_ARQUIVOS


def fatia_turnos_verbatim(total_turnos: int) -> range:
    """Índices 0-based dos últimos `TURNOS_VERBATIM` turnos (ou todos se cabem)."""
    if total_turnos <= 0:
        return range(0)
    inicio = max(0, total_turnos - TURNOS_VERBATIM)
    return range(inicio, total_turnos)


def truncar_ate_tokens(texto: str, teto: int) -> tuple[str, bool]:
    """Corta o texto para caber em `teto` tokens estimados.

    Nunca corta no meio de um codepoint. Retorna `(texto, truncado)`.
    Truncar resultado de tool é permitido (contrato); truncar mensagem de
    usuário/assistente no meio do contexto **não** — isso é `IA-040` em
    `contexto.py`.
    """
    if teto <= 0:
        return ("", True) if texto else ("", False)
    if estimar_tokens(texto) <= teto:
        return texto, False
    # teto tokens ≈ teto * 4 chars; corta e reajusta se a estimativa ainda passar.
    limite_chars = teto * 4
    cortado = texto[:limite_chars]
    while cortado and estimar_tokens(cortado) > teto:
        cortado = cortado[:-1]
    return cortado, True
