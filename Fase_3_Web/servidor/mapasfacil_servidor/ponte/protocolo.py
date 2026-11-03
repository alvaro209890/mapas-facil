"""Protocolo NDJSON da ponte — espelho puro do contrato do núcleo (F1-01/W-04).

O núcleo fala `req` / `res` / `evt` por stdio. O servidor **não importa** o núcleo
(AW-01): este módulo reproduz só o que a ponte precisa para falar com ele, e o
teste `test_protocolo_igual_ao_nucleo` compara os dois envelopes quando o pacote
do núcleo está instalado no mesmo interpretador.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

PROTOCOLO_VERSAO = 1

# Vocabulário fechado de eventos (mesmo do núcleo, F1-01 §Eventos).
EVENTOS: frozenset[str] = frozenset(
    {
        "job.progresso",
        "job.log",
        "job.artefato_parcial",
        "workspace.mudou",
        "chat.delta",
        "chat.raciocinio",
        "chat.tool",
        "chat.pergunta",
        "mapspec.atualizado",
        "aviso",
    }
)


class ProtocoloInvalido(Exception):
    """Linha fora do contrato — o worker é reiniciado (SV-230)."""


def novo_id() -> str:
    """Id de requisição. Opaco: o núcleo usa ULID, aqui basta ser único."""
    return uuid.uuid4().hex


def envelope_req(metodo: str, params: dict[str, Any] | None = None, id_req: str | None = None) -> dict[str, Any]:
    return {
        "v": PROTOCOLO_VERSAO,
        "id": id_req or novo_id(),
        "tipo": "req",
        "metodo": metodo,
        "params": params or {},
    }


def envelope_res(id_req: str, resultado: Any) -> dict[str, Any]:
    return {"v": PROTOCOLO_VERSAO, "id": id_req, "tipo": "res", "ok": True, "resultado": resultado}


def envelope_erro(id_req: str, erro: dict[str, Any]) -> dict[str, Any]:
    return {"v": PROTOCOLO_VERSAO, "id": id_req, "tipo": "res", "ok": False, "erro": erro}


def envelope_evt(id_req: str, evento: str, dados: dict[str, Any]) -> dict[str, Any]:
    if evento not in EVENTOS:
        raise ProtocoloInvalido(
            f"Evento fora do contrato: {evento}. Válidos: {', '.join(sorted(EVENTOS))}"
        )
    return {"v": PROTOCOLO_VERSAO, "id": id_req, "tipo": "evt", "evento": evento, "dados": dados}


def serializar_linha(mensagem: dict[str, Any]) -> str:
    return json.dumps(mensagem, ensure_ascii=False)


def parsear_linha(linha: str) -> dict[str, Any]:
    texto = linha.strip()
    if not texto:
        raise ProtocoloInvalido("Linha vazia.")
    try:
        payload = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ProtocoloInvalido(f"JSON inválido na linha de entrada: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ProtocoloInvalido("Mensagem precisa ser um objeto JSON.")
    tipo = payload.get("tipo")
    if tipo not in {"req", "res", "evt"}:
        raise ProtocoloInvalido(f"Tipo de mensagem inválido: {tipo!r}.")
    return payload
