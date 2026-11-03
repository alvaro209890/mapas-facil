"""SSE por projeto — replay + ao vivo sem buraco e sem duplicata (W-03/W5-02).

A garantia central: a inscrição no fan-out acontece **antes** da leitura do arquivo,
e tudo que o replay já entregou é descartado do fluxo ao vivo pelo `seq`. Assim o
cliente que reconecta com `Last-Event-ID` não perde nem repete evento.

Cada evento vira um bloco SSE:

    id: 1842
    event: mf
    data: {"seq":1842,...}

O heartbeat (`: ♥`) a cada 15 s mantém o túnel da Cloudflare aberto.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from .log import LogEventos

HEARTBEAT_S = 15.0


def formatar_sse(envelope: dict) -> str:
    """Bloco SSE de um evento (com `id:` para o `Last-Event-ID` funcionar)."""
    dados = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    return f"id: {envelope['seq']}\nevent: mf\ndata: {dados}\n\n"


def formatar_heartbeat() -> str:
    return ": ♥\n\n"


@dataclass
class Hub:
    """Fan-out em memória: uma fila por assinante, por projeto."""

    _assinantes: dict[str, set[asyncio.Queue]] = field(default_factory=dict)

    def assinar(self, projeto_id: str) -> asyncio.Queue:
        fila: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._assinantes.setdefault(projeto_id, set()).add(fila)
        return fila

    def desassinar(self, projeto_id: str, fila: asyncio.Queue) -> None:
        assinantes = self._assinantes.get(projeto_id)
        if assinantes is None:
            return
        assinantes.discard(fila)
        if not assinantes:
            self._assinantes.pop(projeto_id, None)

    def publicar(self, projeto_id: str, envelope: dict) -> None:
        for fila in list(self._assinantes.get(projeto_id, ())):
            try:
                fila.put_nowait(envelope)
            except asyncio.QueueFull:
                # Aba travada não pode derrubar a geração: descarta e segue (o
                # replay por `seq` recupera quando ela voltar).
                continue

    def assinantes(self, projeto_id: str) -> int:
        return len(self._assinantes.get(projeto_id, ()))


async def fluxo(
    *,
    raiz_projeto: Path,
    projeto_id: str,
    hub: Hub,
    desde: int = 0,
    heartbeat_s: float = HEARTBEAT_S,
    compactar_desde_zero: bool = True,
    relogio=time.monotonic,
) -> AsyncIterator[str]:
    """Gera os blocos SSE: replay do log, depois ao vivo, com heartbeat."""
    log = LogEventos(raiz_projeto)
    # 1) assina ANTES de ler o arquivo — nenhum evento cai no vão entre as duas coisas.
    fila = hub.assinar(projeto_id)
    ultimo_seq = desde
    try:
        # 2) replay
        eventos = log.ler_desde(desde)
        if desde == 0 and compactar_desde_zero and eventos:
            eventos = log.compactar(eventos)
        for envelope in eventos:
            ultimo_seq = max(ultimo_seq, int(envelope["seq"]))
            yield formatar_sse(envelope)

        # 3) ao vivo
        proximo_heartbeat = relogio() + heartbeat_s
        while True:
            restante = max(0.0, proximo_heartbeat - relogio())
            try:
                envelope = await asyncio.wait_for(fila.get(), timeout=restante)
            except asyncio.TimeoutError:
                yield formatar_heartbeat()
                proximo_heartbeat = relogio() + heartbeat_s
                continue
            seq = int(envelope.get("seq", 0))
            if seq <= ultimo_seq:
                continue  # já foi no replay
            ultimo_seq = seq
            yield formatar_sse(envelope)
            proximo_heartbeat = relogio() + heartbeat_s
    finally:
        hub.desassinar(projeto_id, fila)


def cabecalhos_sse() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream; charset=utf-8",
    }
