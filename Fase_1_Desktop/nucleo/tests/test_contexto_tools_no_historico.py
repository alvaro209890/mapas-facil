# Caso real do site (teste_22, 04/11/2026): a abertura só chamou `perguntar`, a mensagem do
# assistente ficou vazia, e no turno seguinte o modelo não sabia que a fala curta do usuário
# ("Dinâmica de uso do solo") respondia à pergunta dele — e perguntava de novo.

from __future__ import annotations

import json

from mapasfacil_nucleo.agente.contexto import montar_mensagens_llm, nota_das_tools

PERGUNTA = {
    "tool": "perguntar",
    "ok": True,
    "args_resumo": json.dumps(
        {
            "pergunta": "Qual mapa você deseja gerar?",
            "opcoes": [
                {"id": "dinamica_2026_retrato", "rotulo": "Dinâmica de uso do solo"},
                {"id": "tipologia_paisagem", "rotulo": "Tipologia vegetal"},
            ],
        },
        ensure_ascii=False,
    ),
}


def test_turno_so_com_perguntar_chega_ao_modelo_com_a_pergunta_e_as_opcoes():
    mensagens = montar_mensagens_llm(
        mensagens_db=[
            {"seq": 1, "papel": "usuario", "conteudo": "[ORIGEM: sistema] apresente o imóvel"},
            {
                "seq": 2,
                "papel": "assistente",
                "conteudo": "",
                "tool_traces": [{"tool": "listar_modelos_galeria", "ok": True}, PERGUNTA],
            },
            {"seq": 3, "papel": "usuario", "conteudo": "Dinâmica de uso do solo"},
        ],
        compact_summary=None,
    )
    assistente = [m for m in mensagens if m.papel == "assistant"]
    assert len(assistente) == 1
    texto = assistente[0].conteudo
    assert "Qual mapa você deseja gerar?" in texto
    assert "Dinâmica de uso do solo; Tipologia vegetal" in texto
    assert "listar_modelos_galeria" in texto
    assert mensagens[-1].conteudo == "Dinâmica de uso do solo"


def test_sem_tools_a_mensagem_fica_como_esta():
    assert nota_das_tools([]) == ""
    mensagens = montar_mensagens_llm(
        mensagens_db=[{"seq": 1, "papel": "assistente", "conteudo": "Pronto."}],
        compact_summary=None,
    )
    assert mensagens[-1].conteudo == "Pronto."


def test_tool_que_falhou_aparece_marcada_e_args_ruins_nao_quebram():
    nota = nota_das_tools(
        [{"tool": "criar_mapa", "ok": False}, {"tool": "perguntar", "args_resumo": "{truncado"}]
    )
    assert "criar_mapa (falhou)" in nota
    assert "Você perguntou ao usuário" in nota
