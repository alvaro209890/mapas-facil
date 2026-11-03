"""Rota do stream de eventos por projeto (W-03 §Stream de eventos)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from .. import projetos_repo
from ..auth import contas, sessoes
from ..eventos import sse as sse_mod
from . import deps

router = APIRouter(prefix="/projetos", tags=["eventos"])


def _raiz_do_projeto(estado: deps.AppState, projeto_id: str):
    from pathlib import Path

    from ..config import Config

    cfg = estado.config
    if isinstance(cfg, Config):
        return cfg.projetos / projeto_id
    # Sem config (teste) o projeto mora ao lado do banco.
    return Path(str(estado.banco.caminho)).parent / "projetos" / projeto_id


@router.get("/{projeto_id}/eventos")
async def eventos(
    projeto_id: str,
    request: Request,
    desde: int = Query(default=0, ge=0),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """SSE do projeto. Retoma por `?desde=` ou pelo `Last-Event-ID` do navegador."""
    projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=usuario.papel == "admin"
    )
    inicial = desde
    if last_event_id:
        try:
            inicial = max(inicial, int(last_event_id))
        except ValueError:
            pass

    raiz = _raiz_do_projeto(estado, projeto_id)
    gerador = sse_mod.fluxo(
        raiz_projeto=raiz,
        projeto_id=projeto_id,
        hub=estado.hub,
        desde=inicial,
    )
    return StreamingResponse(
        gerador,
        media_type="text/event-stream; charset=utf-8",
        headers=sse_mod.cabecalhos_sse(),
    )
