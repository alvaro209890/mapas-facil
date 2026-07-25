from __future__ import annotations

import json

import pytest

from mapasfacil_nucleo import __main__
from mapasfacil_nucleo.__main__ import processar_linha
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import (
    Roteador,
    envelope_req,
    envelope_res,
    parsear_linha,
)


def test_ping_via_ndjson() -> None:
    linha = json.dumps(envelope_req("ping"))
    resposta = json.loads(processar_linha(linha))
    assert resposta["ok"] is True
    assert resposta["resultado"]["pong"] is True


def test_doctor_via_ndjson() -> None:
    linha = json.dumps(envelope_req("doctor.rodar"))
    resposta = json.loads(processar_linha(linha))
    assert resposta["ok"] is True
    assert "nucleo" in resposta["resultado"]


def test_metodo_desconhecido() -> None:
    linha = json.dumps(envelope_req("nao.existe"))
    resposta = json.loads(processar_linha(linha))
    assert resposta["ok"] is False
    assert resposta["erro"]["codigo"] == "NU-002"


def test_json_invalido() -> None:
    resposta = json.loads(processar_linha("{invalido"))
    assert resposta["ok"] is False
    assert resposta["erro"]["codigo"] == "NU-003"


def test_tipo_mensagem_invalido() -> None:
    roteador = __main__.criar_roteador()
    with pytest.raises(ErroNucleo):
        roteador.despachar({"tipo": "evt", "metodo": "ping", "id": "1"})


def test_params_invalidos() -> None:
    roteador = __main__.criar_roteador()
    with pytest.raises(ErroNucleo):
        roteador.despachar({"tipo": "req", "metodo": "ping", "id": "1", "params": []})


def test_envelope_res_serializa() -> None:
    payload = envelope_res("abc", {"ok": True})
    assert payload["tipo"] == "res" and payload["ok"] is True


def test_parsear_linha_nao_objeto() -> None:
    with pytest.raises(ErroNucleo):
        parsear_linha("[1,2,3]")
