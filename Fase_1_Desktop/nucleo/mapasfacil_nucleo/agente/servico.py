# Handlers NDJSON chat.enviar / chat.cancelar (M7).

from __future__ import annotations

import os
from typing import Any

from mapasfacil_nucleo.agente.anexos import validar_anexos
from mapasfacil_nucleo.agente.orquestrador import executar_turno, pedir_cancelamento
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import Emissor


def gate_sessao(params: dict[str, Any]) -> None:
    """Gate `AUTH-030` antes de gastar token (F1-14 / M5)."""
    del params  # conta_id no request é informativo; a sessão viva está em memória
    from mapasfacil_nucleo import sessao

    sessao.exigir_conectado("enviar mensagem ao chat")


def enviar(params: dict[str, Any], emissor: Emissor) -> dict[str, Any]:
    cid = params.get("conversation_id")
    mensagem = params.get("mensagem")
    if not isinstance(cid, str) or not cid:
        raise ErroNucleo("NU-001", "Parâmetro 'conversation_id' é obrigatório.")
    if not isinstance(mensagem, str) or not mensagem.strip():
        raise ErroNucleo("NU-001", "Parâmetro 'mensagem' é obrigatório.")
    anexos = validar_anexos(params.get("anexos"))
    gate_sessao(params)
    workspace = params.get("workspace")
    max_rodadas = params.get("max_rodadas")
    if max_rodadas is None:
        env_max = os.environ.get("MAPASFACIL_MAX_RODADAS_TOOL")
        max_rodadas = int(env_max) if env_max and env_max.isdigit() else 100
    else:
        max_rodadas = int(max_rodadas)
    limite_falhas = params.get("limite_falhas_consecutivas")
    limite_falhas_int = int(limite_falhas) if limite_falhas is not None else 3
    return executar_turno(
        conversation_id=cid,
        mensagem=mensagem.strip(),
        emissor=emissor,
        anexos=anexos,
        workspace=workspace,
        max_rodadas=max_rodadas,
        limite_falhas_consecutivas=limite_falhas_int,
    )


def cancelar(params: dict[str, Any]) -> dict[str, Any]:
    cid = params.get("conversation_id")
    if not isinstance(cid, str) or not cid:
        raise ErroNucleo("NU-001", "Parâmetro 'conversation_id' é obrigatório.")
    pedir_cancelamento(cid)
    return {"ok": True, "conversation_id": cid}
