from __future__ import annotations

import json
from typing import Any, Callable

import ulid

from mapasfacil_nucleo.config import PROTOCOLO_VERSAO
from mapasfacil_nucleo.erros import ErroNucleo


def novo_id() -> str:
    return str(ulid.new())


def envelope_req(metodo: str, params: dict[str, Any] | None = None, id_req: str | None = None) -> dict[str, Any]:
    return {
        "v": PROTOCOLO_VERSAO,
        "id": id_req or novo_id(),
        "tipo": "req",
        "metodo": metodo,
        "params": params or {},
    }


def envelope_res(id_req: str, resultado: Any) -> dict[str, Any]:
    return {
        "v": PROTOCOLO_VERSAO,
        "id": id_req,
        "tipo": "res",
        "ok": True,
        "resultado": resultado,
    }


def envelope_erro(id_req: str, erro: ErroNucleo | dict[str, Any]) -> dict[str, Any]:
    payload = erro if isinstance(erro, dict) else erro.para_dict()
    return {
        "v": PROTOCOLO_VERSAO,
        "id": id_req,
        "tipo": "res",
        "ok": False,
        "erro": payload,
    }


def envelope_evt(id_req: str, evento: str, dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": PROTOCOLO_VERSAO,
        "id": id_req,
        "tipo": "evt",
        "evento": evento,
        "dados": dados,
    }


def serializar_linha(mensagem: dict[str, Any]) -> str:
    return json.dumps(mensagem, ensure_ascii=False)


def parsear_linha(linha: str) -> dict[str, Any]:
    try:
        payload = json.loads(linha)
    except json.JSONDecodeError as exc:
        raise ErroNucleo("NU-003", "JSON inválido na linha de entrada.") from exc
    if not isinstance(payload, dict):
        raise ErroNucleo("NU-003", "Mensagem precisa ser um objeto JSON.")
    return payload


Handler = Callable[[dict[str, Any]], Any]


class Roteador:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def registrar(self, metodo: str, handler: Handler) -> None:
        self._handlers[metodo] = handler

    def despachar(self, mensagem: dict[str, Any]) -> dict[str, Any]:
        if mensagem.get("tipo") != "req":
            raise ErroNucleo("NU-004", "Tipo de mensagem inválido; esperado 'req'.")
        metodo = mensagem.get("metodo")
        if not isinstance(metodo, str) or not metodo:
            raise ErroNucleo("NU-005", "Campo 'metodo' ausente ou inválido.")
        handler = self._handlers.get(metodo)
        if handler is None:
            raise ErroNucleo(
                "NU-002",
                f"Método desconhecido: {metodo}",
                {"metodo": metodo},
            )
        id_req = mensagem.get("id")
        if not isinstance(id_req, str) or not id_req:
            id_req = novo_id()
        params = mensagem.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ErroNucleo("NU-006", "Campo 'params' precisa ser um objeto.")
        try:
            resultado = handler(params)
        except ErroNucleo as exc:
            return envelope_erro(id_req, exc)
        return envelope_res(id_req, resultado)
