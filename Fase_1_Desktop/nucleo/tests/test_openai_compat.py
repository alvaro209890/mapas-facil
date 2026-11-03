# W5-16 — cliente `openai_compat` (9Router) no fio, sem 9Router e sem chave.
#
# O que este arquivo prova de verdade: o **corpo da requisição** que sai (modelo,
# `reasoning_effort`, tools) e a **leitura do SSE** (texto, `reasoning_content`, tool calls
# montadas por índice, `finish_reason`). O smoke ao vivo contra o 9Router é outro teste, o
# do anel 3 — e depende da chave dedicada do Mapas Fácil.

from __future__ import annotations

import json
from typing import Any

import pytest

from mapasfacil_nucleo.agente import openai_compat
from mapasfacil_nucleo.agente.openai_compat import OpenAICompatProvedor
from mapasfacil_nucleo.agente.provedor import MensagemLLM
from mapasfacil_nucleo.erros import ErroNucleo

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "gerar_mapa",
            "description": "Gera o mapa",
            "parameters": {"type": "object", "properties": {"saidas": {"type": "array"}}},
        },
    }
]

LINHAS_SSE = [
    'data: {"choices":[{"delta":{"reasoning_content":"vou olhar a pasta"}}]}\n',
    'data: {"choices":[{"delta":{"content":"Olhando"}}]}\n',
    'data: {"choices":[{"delta":{"content":" a pasta."}}]}\n',
    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_a","function":{"name":"gerar_mapa","arguments":"{\\"saidas\\":"}}]}}]}\n',
    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"[\\"pdf\\"]}"}}]}}]}\n',
    'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}\n',
    "data: [DONE]\n",
]


class _Resposta:
    def __init__(self, linhas: list[str]) -> None:
        self._linhas = [linha.encode("utf-8") for linha in linhas]
        self.fechada = False

    def __iter__(self):
        return iter(self._linhas)

    def close(self) -> None:
        self.fechada = True


class _UrlOpen:
    """Guarda o corpo enviado e devolve o SSE do roteiro."""

    def __init__(self, linhas: list[str]) -> None:
        self.linhas = linhas
        self.corpos: list[dict[str, Any]] = []
        self.cabecalhos: list[dict[str, str]] = []
        self.url = ""

    def __call__(self, req, timeout=None):  # noqa: ANN001 - assinatura do urlopen
        self.url = req.full_url
        self.corpos.append(json.loads(req.data.decode("utf-8")))
        self.cabecalhos.append(dict(req.header_items()))
        return _Resposta(self.linhas)


def _provedor(**kwargs) -> tuple[OpenAICompatProvedor, _UrlOpen]:
    urlopen = _UrlOpen(kwargs.pop("linhas", LINHAS_SSE))
    provedor = OpenAICompatProvedor("chave-de-teste", urlopen=urlopen, **kwargs)
    return provedor, urlopen


def test_endpoint_e_montado_a_partir_do_base_url():
    assert openai_compat.endpoint_de("http://100.104.255.35:20128/v1") == (
        "http://100.104.255.35:20128/v1/chat/completions"
    )
    assert openai_compat.endpoint_de("http://h/v1/") == "http://h/v1/chat/completions"


def test_corpo_leva_modelo_raciocinio_e_tools():
    provedor, urlopen = _provedor()
    list(
        provedor.enviar_stream(
            [MensagemLLM(papel="user", conteudo="faz a dinâmica")],
            tools=TOOLS,
        )
    )
    corpo = urlopen.corpos[0]
    assert corpo["model"] == "ag/gemini-3.8-flash-high"
    assert corpo["reasoning_effort"] == "high"
    assert corpo["stream"] is True
    assert corpo["tool_choice"] == "auto"
    assert corpo["tools"][0]["function"]["name"] == "gerar_mapa"
    assert "temperature" not in corpo
    assert urlopen.url.endswith("/chat/completions")
    assert urlopen.cabecalhos[0]["Authorization"] == "Bearer chave-de-teste"


def test_sse_entrega_texto_raciocinio_e_tool_calls():
    provedor, _ = _provedor()
    pedacos = list(
        provedor.enviar_stream(
            [MensagemLLM(papel="user", conteudo="faz a dinâmica")], tools=TOOLS
        )
    )
    texto = "".join(p.texto for p in pedacos)
    raciocinio = "".join(p.raciocinio for p in pedacos)
    assert texto == "Olhando a pasta."
    assert raciocinio == "vou olhar a pasta"
    final = pedacos[-1]
    assert final.finish_reason == "tool_calls"
    assert final.truncado is False
    assert len(final.tool_calls) == 1
    chamada = final.tool_calls[0]
    assert chamada["id"] == "call_a"
    assert chamada["function"]["name"] == "gerar_mapa"
    # argumentos chegam partidos no SSE e precisam sair JSON válido
    assert json.loads(chamada["function"]["arguments"]) == {"saidas": ["pdf"]}


def test_finish_length_marca_truncado():
    linhas = [
        'data: {"choices":[{"delta":{"content":"cortei aqui"}}]}\n',
        'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n',
        "data: [DONE]\n",
    ]
    provedor, _ = _provedor(linhas=linhas)
    pedacos = list(provedor.enviar_stream([MensagemLLM(papel="user", conteudo="oi")]))
    assert pedacos[-1].truncado is True
    assert pedacos[-1].finish_reason == "length"


def test_cancelar_para_no_meio():
    provedor, _ = _provedor()
    gerado = provedor.enviar_stream([MensagemLLM(papel="user", conteudo="oi")])
    next(gerado)          # primeiro pedaço
    provedor.cancelar()
    restantes = list(gerado)
    assert all(p.texto == "" for p in restantes)


def test_sem_raciocinio_nao_manda_o_campo():
    provedor, urlopen = _provedor(reasoning_effort=None)
    list(provedor.enviar_stream([MensagemLLM(papel="user", conteudo="oi")]))
    assert "reasoning_effort" not in urlopen.corpos[0]


# ------------------------------------------------------------------- do_ambiente


def test_do_ambiente_le_as_variaveis_do_servidor_env():
    provedor = openai_compat.do_ambiente(
        {
            "MAPASFACIL_PROVEDOR_CHAVE": "dedicada",
            "MAPASFACIL_PROVEDOR_URL": "http://10.0.0.1:20128/v1",
            "MAPASFACIL_MODELO_CHAT": "ag/gemini-3.8-flash-high",
            "MAPASFACIL_RACIOCINIO": "high",
        }
    )
    assert provedor.chave == "dedicada"
    assert provedor.endpoint == "http://10.0.0.1:20128/v1/chat/completions"
    assert provedor.modelo == "ag/gemini-3.8-flash-high"
    assert provedor.reasoning_effort == "high"


def test_do_ambiente_recusa_sem_chave():
    with pytest.raises(ErroNucleo) as exc:
        openai_compat.do_ambiente({})
    assert exc.value.codigo == "IA-001"


def test_modelo_rapido_cai_no_do_chat():
    assert openai_compat.modelo_rapido({"MAPASFACIL_MODELO_CHAT": "x"}) == "x"
    assert openai_compat.modelo_rapido({"MAPASFACIL_MODELO_RAPIDO": "y", "MAPASFACIL_MODELO_CHAT": "x"}) == "y"
    assert openai_compat.modelo_rapido({}) == openai_compat.MODELO_PADRAO


def test_contexto_max_do_ambiente():
    assert openai_compat.contexto_max({"MAPASFACIL_CONTEXTO_MAX": "200000"}) == 200000
    assert openai_compat.contexto_max({"MAPASFACIL_CONTEXTO_MAX": ""}) is None
    assert openai_compat.contexto_max({"MAPASFACIL_CONTEXTO_MAX": "muito"}) is None
