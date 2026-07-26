# Asserts de vazamento no payload do LLM (F1-06 / R18).

from __future__ import annotations

import pytest

from mapasfacil_nucleo.agente.contexto import assert_sem_vazamento, montar_mensagens_llm, serializar_payload
from mapasfacil_nucleo.conversas.redator import redigir


def test_payload_sem_wkt_cpf_caminho_chave():
    msgs = montar_mensagens_llm(
        mensagens_db=[
            {
                "seq": 1,
                "papel": "usuario",
                "conteudo": redigir(
                    "veja POLYGON((0 0,1 0,1 1,0 1,0 0)) CPF 111.222.333-44 "
                    "api_key=PLAK11beb31d00294d84a41c2efdf5836a61 authkey=abc "
                    r"C:\Users\alguem\projeto"
                ),
            }
        ],
        compact_summary=None,
    )
    payload = serializar_payload(msgs)
    assert_sem_vazamento(payload)


def test_assert_sem_vazamento_detecta():
    with pytest.raises(AssertionError):
        assert_sem_vazamento("MULTIPOLYGON(((")
    with pytest.raises(AssertionError):
        assert_sem_vazamento("123.456.789-00")
    with pytest.raises(AssertionError):
        assert_sem_vazamento(r"C:\\Users\\x")
    with pytest.raises(AssertionError):
        assert_sem_vazamento("PLAK123")
