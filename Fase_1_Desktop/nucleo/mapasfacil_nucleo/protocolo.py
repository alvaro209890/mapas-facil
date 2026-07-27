from __future__ import annotations

import json
import threading
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


# Vocabulário fechado de eventos (F1-01 §Eventos). Emitir nome fora desta lista é
# erro de programação: a UI só sabe consumir o que está no contrato, e evento
# inventado vira animação órfã (AP-07). Nome novo entra aqui **e** no plano.
#
# `chat.pergunta` (F1-06 §Pergunta ao usuário): o agente pede uma escolha
# estruturada em vez de reformular tudo em texto livre — ver
# Fase_1_Desktop/planos/06-agente-eng-florestal.md.
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


def evento_valido(evento: str) -> bool:
    return evento in EVENTOS


def envelope_evt(id_req: str, evento: str, dados: dict[str, Any]) -> dict[str, Any]:
    if not evento_valido(evento):
        raise ValueError(
            f"Evento fora do contrato F1-01: {evento}. "
            f"Válidos: {', '.join(sorted(EVENTOS))}"
        )
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


class Emissor:
    """Canal de eventos (`tipo:"evt"`) de uma requisição em andamento.

    O `id` do evento é o da requisição que o gerou (F1-01 §Protocolo). Sem `sink`,
    emitir é no-op — é o caso de quem chama o núcleo como biblioteca.
    """

    def __init__(self, id_req: str, sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.id_req = id_req
        self._sink = sink

    def emitir(self, evento: str, dados: dict[str, Any]) -> dict[str, Any]:
        envelope = envelope_evt(self.id_req, evento, dados)
        if self._sink is not None:
            self._sink(envelope)
        return envelope


# Sink do loop NDJSON para eventos **fora** de uma req (A12: `workspace.mudou`).
# O `id` do envelope é um ULID próprio — não há req pai.
_sink_assincrono: Callable[[dict[str, Any]], None] | None = None
_sink_assincrono_lock = threading.Lock()


def configurar_sink_assincrono(
    sink: Callable[[dict[str, Any]], None] | None,
) -> None:
    """Liga/desliga o canal de eventos não solicitados (watcher, avisos futuros)."""
    global _sink_assincrono
    with _sink_assincrono_lock:
        _sink_assincrono = sink


def emitir_assincrono(
    evento: str,
    dados: dict[str, Any],
    *,
    id_evt: str | None = None,
) -> dict[str, Any]:
    """Emite `tipo:"evt"` pelo sink do loop stdio, thread-safe.

    Sem sink configurado (biblioteca / testes unitários) é no-op além de devolver
    o envelope — espelha o contrato do `Emissor` sem req.
    """
    envelope = envelope_evt(id_evt or novo_id(), evento, dados)
    with _sink_assincrono_lock:
        sink = _sink_assincrono
    if sink is not None:
        sink(envelope)
    return envelope


Handler = Callable[[dict[str, Any]], Any]
HandlerComEventos = Callable[[dict[str, Any], Emissor], Any]


class Roteador:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler | HandlerComEventos] = {}
        self._com_eventos: set[str] = set()

    def registrar(
        self,
        metodo: str,
        handler: Handler | HandlerComEventos,
        *,
        com_eventos: bool = False,
    ) -> None:
        """`com_eventos=True` faz o handler receber `(params, emissor)`."""
        self._handlers[metodo] = handler
        if com_eventos:
            self._com_eventos.add(metodo)
        else:
            self._com_eventos.discard(metodo)

    def despachar(
        self,
        mensagem: dict[str, Any],
        emitir: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
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
            if metodo in self._com_eventos:
                resultado = handler(params, Emissor(id_req, emitir))
            else:
                resultado = handler(params)
        except ErroNucleo as exc:
            return envelope_erro(id_req, exc)
        return envelope_res(id_req, resultado)
