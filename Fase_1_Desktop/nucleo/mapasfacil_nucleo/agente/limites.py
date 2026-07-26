"""Orçamento de contexto do agente — constantes vinculantes (G2 / F1-06).

Teto e códigos de erro vivem aqui. O pipeline compactar → resumir → recusar
(`IA-040`) fica em `contexto.py`; este módulo só exporta números e helpers puros
(sem I/O, sem rede, sem `raise ErroNucleo`).

Estimativa de tokens no anel 1: `ceil(len / 4)` sobre texto (codepoints Unicode) —
heurística determinística, sem tiktoken. Não é a contagem do provedor; serve para
gates internos de compressão e truncamento.
"""

from __future__ import annotations

import json
import math
from typing import Any, Final, TypedDict

# --------------------------------------------------------------------------- tetos (F1-06)

ENTRADA_MAX_POR_TURNO: Final = 60_000
SAIDA_MAX_TOKENS: Final = 8_000
RODADAS_TOOL_MAX_POR_TURNO: Final = 12
TOKENS_CONVERSA_MAX: Final = 400_000
RESULTADO_TOOL_MAX: Final = 2_000
MEMORIA_TRABALHO_MAX: Final = 1_200
COMPACT_SUMMARY_MAX: Final = 800
TURNOS_VERBATIM: Final = 8
TURNOS_VERBATIM_APOS_RESUMIR: Final = 4  # fase RESUMIR do pipeline (8 → 4)
SYSTEM_PROMPT_MAX: Final = 2_500
COMPACT_SUMMARY_REGENERAR_CADA: Final = 6
MAPSPEC_DIFF_MAX: Final = 2_000
INDICE_WORKSPACE_MAX_ARQUIVOS: Final = 80

# --------------------------------------------------------------------------- códigos IA-*

CODIGO_SEM_CHAVE: Final = "IA-001"
CODIGO_PROVEDOR_INDISPONIVEL: Final = "IA-010"
CODIGO_TOOL_INEXISTENTE: Final = "IA-020"
CODIGO_LIMITE_RODADAS: Final = "IA-030"
CODIGO_CONTEXTO_EXCEDIDO: Final = "IA-040"
CODIGO_TETO_CONVERSA: Final = "IA-041"
CODIGO_RESPOSTA_TRUNCADA: Final = "IA-050"
CODIGO_VISAO_INDISPONIVEL: Final = "IA-060"
CODIGO_VISAO_RESPOSTA_INVALIDA: Final = "IA-061"

# --------------------------------------------------------------------------- tipos


class ResultadoToolTruncado(TypedDict):
    """Envelope do resultado de tool após o teto de `RESULTADO_TOOL_MAX`.

    `ponteiro` aponta para o artefato completo (caminho relativo à pasta do
    projeto ou id interno) quando `truncado` é True; vazio se coube inteiro.
    """

    conteudo: str
    truncado: bool
    ponteiro: str
    tokens_estimados: int


__all__ = (
    "ENTRADA_MAX_POR_TURNO",
    "SAIDA_MAX_TOKENS",
    "RODADAS_TOOL_MAX_POR_TURNO",
    "TOKENS_CONVERSA_MAX",
    "RESULTADO_TOOL_MAX",
    "MEMORIA_TRABALHO_MAX",
    "COMPACT_SUMMARY_MAX",
    "TURNOS_VERBATIM",
    "TURNOS_VERBATIM_APOS_RESUMIR",
    "SYSTEM_PROMPT_MAX",
    "COMPACT_SUMMARY_REGENERAR_CADA",
    "MAPSPEC_DIFF_MAX",
    "INDICE_WORKSPACE_MAX_ARQUIVOS",
    "CODIGO_SEM_CHAVE",
    "CODIGO_PROVEDOR_INDISPONIVEL",
    "CODIGO_TOOL_INEXISTENTE",
    "CODIGO_LIMITE_RODADAS",
    "CODIGO_CONTEXTO_EXCEDIDO",
    "CODIGO_TETO_CONVERSA",
    "CODIGO_RESPOSTA_TRUNCADA",
    "CODIGO_VISAO_INDISPONIVEL",
    "CODIGO_VISAO_RESPOSTA_INVALIDA",
    "ResultadoToolTruncado",
    "estimar_tokens",
    "estimar_tokens_json",
    "cabe_em",
    "excede_entrada_turno",
    "excede_conversa",
    "excede_saida",
    "excede_memoria_trabalho",
    "excede_compact_summary",
    "excede_system_prompt",
    "rodada_tool_permitida",
    "rodada_tool_excedida",
    "deve_regenerar_compact_summary",
    "mapspec_diff_cabe",
    "indice_precisa_resumo",
    "turnos_verbatim_para_fase",
    "fatia_turnos_verbatim",
    "truncar_ate_tokens",
    "truncar_resultado_tool",
)

# --------------------------------------------------------------------------- helpers


def estimar_tokens(texto: str) -> int:
    """Heurística anel 1: ~1 token por 4 codepoints (arredonda para cima)."""
    if not texto:
        return 0
    return math.ceil(len(texto) / 4)


def estimar_tokens_json(obj: Any) -> int:
    """Tokens estimados do JSON serializado de forma estável (`sort_keys`).

    Valores não serializáveis viram `str(obj)` via `default=str`, para o helper
    nunca levantar `TypeError` no pipeline de contexto.
    """
    serializado = json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return estimar_tokens(serializado)


def cabe_em(tokens: int, teto: int) -> bool:
    """`True` se `tokens` (não negativo) cabe no teto. Contagem negativa = não cabe."""
    if tokens < 0:
        return False
    return tokens <= teto


def excede_entrada_turno(tokens: int) -> bool:
    return not cabe_em(tokens, ENTRADA_MAX_POR_TURNO)


def excede_conversa(tokens_acumulados: int) -> bool:
    return not cabe_em(tokens_acumulados, TOKENS_CONVERSA_MAX)


def excede_saida(tokens: int) -> bool:
    return not cabe_em(tokens, SAIDA_MAX_TOKENS)


def excede_memoria_trabalho(tokens: int) -> bool:
    return not cabe_em(tokens, MEMORIA_TRABALHO_MAX)


def excede_compact_summary(tokens: int) -> bool:
    return not cabe_em(tokens, COMPACT_SUMMARY_MAX)


def excede_system_prompt(tokens: int) -> bool:
    return not cabe_em(tokens, SYSTEM_PROMPT_MAX)


def rodada_tool_permitida(rodada: int) -> bool:
    """Rodadas **1..12** inclusive (1-based). A 13ª dispara `IA-030`.

    Contadores 0-based devem somar 1 antes de chamar (ou usar
    `rodada_tool_excedida(indice_0based + 1)`).
    """
    return 1 <= rodada <= RODADAS_TOOL_MAX_POR_TURNO


def rodada_tool_excedida(rodada: int) -> bool:
    """Inverso de `rodada_tool_permitida` — handy para levantar `IA-030`."""
    return not rodada_tool_permitida(rodada)


def deve_regenerar_compact_summary(turnos_desde_ultimo: int) -> bool:
    """Regenera quando ≥ `COMPACT_SUMMARY_REGENERAR_CADA` turnos novos passaram.

    `0` = acabou de regenerar (ou conversa nova sem resumo ainda — quem decide
    gerar o primeiro é `resumo.py`, não este gate).
    """
    return turnos_desde_ultimo >= COMPACT_SUMMARY_REGENERAR_CADA


def mapspec_diff_cabe(tokens_diff: int) -> bool:
    """Diff ≤ 2000 tokens vai no payload; acima manda o MapSpec completo de novo."""
    return cabe_em(tokens_diff, MAPSPEC_DIFF_MAX)


def indice_precisa_resumo(n_arquivos: int) -> bool:
    """Acima de 80 arquivos o índice completo cede a resumo por tipo/papel."""
    return n_arquivos > INDICE_WORKSPACE_MAX_ARQUIVOS


def turnos_verbatim_para_fase(*, apos_resumir: bool = False) -> int:
    """8 na montagem normal; 4 na fase RESUMIR do pipeline de estouro."""
    if apos_resumir:
        return TURNOS_VERBATIM_APOS_RESUMIR
    return TURNOS_VERBATIM


def fatia_turnos_verbatim(
    total_turnos: int,
    *,
    limite: int | None = None,
) -> range:
    """Índices 0-based dos últimos `limite` turnos (default: `TURNOS_VERBATIM`).

    Na fase RESUMIR passe `limite=TURNOS_VERBATIM_APOS_RESUMIR` (ou use
    `turnos_verbatim_para_fase(apos_resumir=True)`).
    """
    if total_turnos <= 0:
        return range(0)
    n = TURNOS_VERBATIM if limite is None else limite
    if n <= 0:
        return range(0)
    inicio = max(0, total_turnos - n)
    return range(inicio, total_turnos)


def truncar_ate_tokens(texto: str, teto: int) -> tuple[str, bool]:
    """Corta o texto para caber em `teto` tokens estimados.

    Nunca corta no meio de um codepoint (slice de `str` em Python). Retorna
    `(texto, truncado)`. Teto ≤ 0 ⇒ `("", True)` se havia texto, senão
    `("", True)` também — teto inválido conta como truncamento forçado.

    Preferir `truncar_resultado_tool` para resultados de tool (envelope com
    ponteiro). Truncar mensagem de usuário/assistente no contexto **não** —
    isso é `IA-040` em `contexto.py`.
    """
    if teto <= 0:
        return "", True
    if estimar_tokens(texto) <= teto:
        return texto, False
    # teto tokens ≈ teto * 4 codepoints; reajusta se a estimativa ainda passar.
    limite_chars = teto * 4
    cortado = texto[:limite_chars]
    while cortado and estimar_tokens(cortado) > teto:
        cortado = cortado[:-1]
    return cortado, True


def truncar_resultado_tool(texto: str, *, ponteiro: str) -> ResultadoToolTruncado:
    """Aplica `RESULTADO_TOOL_MAX` e devolve o envelope F1-06 (`truncado` + ponteiro).

    `ponteiro` é obrigatório no contrato quando trunca (caminho relativo ou id);
    se o texto couber, o ponteiro volta vazio para o consumidor não seguir link.
    """
    conteudo, truncado = truncar_ate_tokens(texto, RESULTADO_TOOL_MAX)
    return {
        "conteudo": conteudo,
        "truncado": truncado,
        "ponteiro": ponteiro if truncado else "",
        "tokens_estimados": estimar_tokens(conteudo),
    }
