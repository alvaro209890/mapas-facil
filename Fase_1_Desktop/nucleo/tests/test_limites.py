"""G2 — orçamento de contexto em `agente/limites.py` (F1-06)."""

from __future__ import annotations

from datetime import datetime

import pytest

from mapasfacil_nucleo.agente import limites


# --------------------------------------------------------------------------- constantes


def test_tetos_f106() -> None:
    assert limites.ENTRADA_MAX_POR_TURNO == 60_000
    assert limites.SAIDA_MAX_TOKENS == 8_000
    assert limites.RODADAS_TOOL_MAX_POR_TURNO == 12
    assert limites.TOKENS_CONVERSA_MAX == 400_000
    assert limites.RESULTADO_TOOL_MAX == 2_000
    assert limites.MEMORIA_TRABALHO_MAX == 1_200
    assert limites.COMPACT_SUMMARY_MAX == 800
    assert limites.TURNOS_VERBATIM == 8
    assert limites.TURNOS_VERBATIM_APOS_RESUMIR == 4
    assert limites.SYSTEM_PROMPT_MAX == 2_500
    assert limites.COMPACT_SUMMARY_REGENERAR_CADA == 6
    assert limites.MAPSPEC_DIFF_MAX == 2_000
    assert limites.INDICE_WORKSPACE_MAX_ARQUIVOS == 80


def test_codigos_ia() -> None:
    assert limites.CODIGO_SEM_CHAVE == "IA-001"
    assert limites.CODIGO_PROVEDOR_INDISPONIVEL == "IA-010"
    assert limites.CODIGO_TOOL_INEXISTENTE == "IA-020"
    assert limites.CODIGO_LIMITE_RODADAS == "IA-030"
    assert limites.CODIGO_CONTEXTO_EXCEDIDO == "IA-040"
    assert limites.CODIGO_TETO_CONVERSA == "IA-041"
    assert limites.CODIGO_RESPOSTA_TRUNCADA == "IA-050"


def test_all_exporta_simbolos_publicos() -> None:
    for nome in limites.__all__:
        assert hasattr(limites, nome), nome


# --------------------------------------------------------------------------- estimativa


def test_estimar_tokens_vazios_e_basicos() -> None:
    assert limites.estimar_tokens("") == 0
    assert limites.estimar_tokens("abcd") == 1
    assert limites.estimar_tokens("abcde") == 2  # ceil(5/4)


def test_estimar_tokens_unicode_por_codepoint() -> None:
    # 4 codepoints → 1 token (emoji e acento contam 1 cada, não bytes).
    assert limites.estimar_tokens("áéíó") == 1
    assert limites.estimar_tokens("😀😁😂🤣") == 1
    assert limites.estimar_tokens("中文測試") == 1


def test_estimar_tokens_json_estavel() -> None:
    obj = {"b": 2, "a": [1, {"z": True}]}
    a = limites.estimar_tokens_json(obj)
    b = limites.estimar_tokens_json({"a": [1, {"z": True}], "b": 2})
    assert a == b
    assert a > 0


def test_estimar_tokens_json_nao_serializavel_nao_levanta() -> None:
    tokens = limites.estimar_tokens_json({"quando": datetime(2026, 7, 26), "s": {1, 2}})
    assert tokens > 0


# --------------------------------------------------------------------------- gates


def test_cabe_em_e_excede_entrada() -> None:
    assert limites.cabe_em(60_000, limites.ENTRADA_MAX_POR_TURNO) is True
    assert limites.excede_entrada_turno(60_000) is False
    assert limites.excede_entrada_turno(60_001) is True


def test_cabe_em_rejeita_contagem_negativa() -> None:
    assert limites.cabe_em(-1, 100) is False
    assert limites.excede_entrada_turno(-1) is True
    assert limites.excede_conversa(-1) is True


def test_excede_conversa() -> None:
    assert limites.excede_conversa(400_000) is False
    assert limites.excede_conversa(400_001) is True


def test_excede_tetos_auxiliares() -> None:
    assert limites.excede_saida(8_000) is False
    assert limites.excede_saida(8_001) is True
    assert limites.excede_memoria_trabalho(1_200) is False
    assert limites.excede_memoria_trabalho(1_201) is True
    assert limites.excede_compact_summary(800) is False
    assert limites.excede_compact_summary(801) is True
    assert limites.excede_system_prompt(2_500) is False
    assert limites.excede_system_prompt(2_501) is True


def test_rodada_tool_1_a_12_ok_13_nao() -> None:
    assert limites.rodada_tool_permitida(1) is True
    assert limites.rodada_tool_permitida(12) is True
    assert limites.rodada_tool_permitida(13) is False
    assert limites.rodada_tool_permitida(0) is False
    assert limites.rodada_tool_excedida(12) is False
    assert limites.rodada_tool_excedida(13) is True


def test_deve_regenerar_compact_summary() -> None:
    assert limites.deve_regenerar_compact_summary(0) is False
    assert limites.deve_regenerar_compact_summary(5) is False
    assert limites.deve_regenerar_compact_summary(6) is True
    assert limites.deve_regenerar_compact_summary(7) is True


def test_mapspec_diff_e_indice() -> None:
    assert limites.mapspec_diff_cabe(2_000) is True
    assert limites.mapspec_diff_cabe(2_001) is False
    assert limites.indice_precisa_resumo(80) is False
    assert limites.indice_precisa_resumo(81) is True


def test_turnos_verbatim_para_fase() -> None:
    assert limites.turnos_verbatim_para_fase() == 8
    assert limites.turnos_verbatim_para_fase(apos_resumir=True) == 4


def test_fatia_turnos_verbatim_ultimos_8() -> None:
    assert list(limites.fatia_turnos_verbatim(0)) == []
    assert list(limites.fatia_turnos_verbatim(5)) == [0, 1, 2, 3, 4]
    assert list(limites.fatia_turnos_verbatim(8)) == list(range(8))
    assert list(limites.fatia_turnos_verbatim(120)) == list(range(112, 120))
    assert len(list(limites.fatia_turnos_verbatim(120))) == limites.TURNOS_VERBATIM


def test_fatia_turnos_verbatim_fase_resumir() -> None:
    fatia = limites.fatia_turnos_verbatim(
        120, limite=limites.turnos_verbatim_para_fase(apos_resumir=True)
    )
    assert list(fatia) == list(range(116, 120))
    assert len(list(fatia)) == 4


# --------------------------------------------------------------------------- truncar


def test_truncar_ate_tokens_abaixo_do_teto() -> None:
    texto = "ok"
    saida, truncado = limites.truncar_ate_tokens(texto, limites.RESULTADO_TOOL_MAX)
    assert saida == texto
    assert truncado is False


def test_truncar_ate_tokens_acima_do_teto() -> None:
    texto = "x" * (limites.RESULTADO_TOOL_MAX * 4 + 4)
    assert limites.estimar_tokens(texto) > limites.RESULTADO_TOOL_MAX
    saida, truncado = limites.truncar_ate_tokens(texto, limites.RESULTADO_TOOL_MAX)
    assert truncado is True
    assert limites.estimar_tokens(saida) == limites.RESULTADO_TOOL_MAX
    assert len(saida) < len(texto)


def test_truncar_ate_tokens_unicode_nao_quebra_codepoint() -> None:
    # 3 tokens de margem: 12 codepoints; teto 2 → 8 codepoints.
    texto = "áéíó😀😁😂🤣中文測試"
    assert len(texto) == 12
    saida, truncado = limites.truncar_ate_tokens(texto, 2)
    assert truncado is True
    assert len(saida) == 8
    assert limites.estimar_tokens(saida) == 2
    # Todos os chars restantes são codepoints válidos da string original.
    assert saida == texto[:8]


@pytest.mark.parametrize("teto", [0, -1])
def test_truncar_teto_nao_positivo(teto: int) -> None:
    saida, truncado = limites.truncar_ate_tokens("abc", teto)
    assert saida == ""
    assert truncado is True
    # texto vazio + teto inválido também marca truncado (teto inválido).
    saida2, truncado2 = limites.truncar_ate_tokens("", teto)
    assert saida2 == ""
    assert truncado2 is True


def test_truncar_resultado_tool_envelope() -> None:
    curto = limites.truncar_resultado_tool("ok", ponteiro="artefatos/x.json")
    assert curto["truncado"] is False
    assert curto["conteudo"] == "ok"
    assert curto["ponteiro"] == ""
    assert curto["tokens_estimados"] == 1

    longo = "y" * (limites.RESULTADO_TOOL_MAX * 4 + 40)
    env = limites.truncar_resultado_tool(longo, ponteiro="artefatos/tool_42.json")
    assert env["truncado"] is True
    assert env["ponteiro"] == "artefatos/tool_42.json"
    assert limites.estimar_tokens(env["conteudo"]) <= limites.RESULTADO_TOOL_MAX
    assert env["tokens_estimados"] == limites.estimar_tokens(env["conteudo"])
