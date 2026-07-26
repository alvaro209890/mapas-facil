# Handlers NDJSON chat.enviar / chat.cancelar (M7).

from __future__ import annotations

from typing import Any

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
    anexos = params.get("anexos")
    if anexos is not None and not isinstance(anexos, list):
        raise ErroNucleo("NU-001", "Parâmetro 'anexos' inválido.")
    gate_sessao(params)
    return executar_turno(
        conversation_id=cid,
        mensagem=mensagem.strip(),
        emissor=emissor,
        anexos=anexos,
    )


def cancelar(params: dict[str, Any]) -> dict[str, Any]:
    cid = params.get("conversation_id")
    if not isinstance(cid, str) or not cid:
        raise ErroNucleo("NU-001", "Parâmetro 'conversation_id' é obrigatório.")
    pedir_cancelamento(cid)
    return {"ok": True, "conversation_id": cid}
