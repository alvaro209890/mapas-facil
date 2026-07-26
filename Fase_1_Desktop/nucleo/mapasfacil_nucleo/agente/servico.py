# Handlers NDJSON chat.enviar / chat.cancelar (M7).

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.agente.orquestrador import executar_turno, pedir_cancelamento
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import Emissor


def gate_sessao(params: dict[str, Any]) -> None:
    """Gancho do gate `AUTH-030` — **não** implementa autenticação (é M5).

    Quando `nucleo/sessao.py` existir ([F1-14](../../planos/14-auth-e-conta.md)),
    a validação entra aqui e recusa antes de gastar token do usuário:

    ```python
    if not sessao.valida(params.get("conta_id")):
        raise ErroNucleo("AUTH-030", "Sessão inválida. Entre na sua conta.")
    ```

    Até lá é um no-op deliberado: M7 não depende de rede de identidade, e
    inventar um gate meia-boca agora só criaria caminho morto para o M5 remover.
    """
    del params


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
    gate_sessao(params)  # AUTH-030 — no-op até M5 (ver docstring)
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
