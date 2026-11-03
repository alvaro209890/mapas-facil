"""Chat do projeto — um turno por vez, streaming pelo SSE (W-05/W5-10/W5-11)."""

from __future__ import annotations

import asyncio
import sqlite3
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from .. import projetos_repo
from ..auth import contas, sessoes
from ..erros import ErroServidor
from ..eventos.log import LogEventos
from . import deps, modelos

router = APIRouter(prefix="/projetos", tags=["chat"])


def _raiz(estado: deps.AppState, projeto_id: str):
    from pathlib import Path

    from ..config import Config

    cfg = estado.config
    if isinstance(cfg, Config):
        return cfg.projetos / projeto_id
    return Path(str(estado.banco.caminho)).parent / "projetos" / projeto_id


def _exigir_pool(estado: deps.AppState):
    pool = getattr(estado, "pool", None)
    if pool is None:
        raise ErroServidor(
            "SV-240",
            "O motor de geração não está configurado neste servidor.",
            status_http=503,
            porque="Sem o pool de workers não há como conversar com o núcleo.",
            o_que_fazer="Confira MF_PYTHON_NUCLEO e reinicie o serviço.",
        )
    return pool


def _conversa_do_projeto(con: sqlite3.Connection, projeto_id: str) -> str | None:
    linha = con.execute(
        "SELECT conversa_id FROM projetos WHERE id = ?", (projeto_id,)
    ).fetchone()
    return linha["conversa_id"] if linha else None


def _guardar_conversa(con: sqlite3.Connection, projeto_id: str, conversa_id: str) -> None:
    con.execute(
        "UPDATE projetos SET conversa_id = ? WHERE id = ?", (conversa_id, projeto_id)
    )


def _emitir(
    *,
    raiz,
    hub,
    projeto_id: str,
    evento: str,
    dados: dict,
    req_id: str | None = None,
    job_id: str | None = None,
    origem: str = "servidor",
) -> dict:
    envelope = LogEventos(raiz).registrar(
        origem=origem, evento=evento, dados=dados, req_id=req_id, job_id=job_id
    )
    hub.publicar(projeto_id, envelope)
    return envelope


@router.get("/{projeto_id}/mensagens")
async def listar_mensagens(
    projeto_id: str,
    antes: int | None = Query(default=None, ge=1),
    limite: int = Query(default=50, ge=1, le=200),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=usuario.papel == "admin"
    )
    conversa_id = _conversa_do_projeto(con, projeto.id)
    if not conversa_id:
        return {"itens": [], "proximo": None}

    pool = _exigir_pool(estado)
    try:
        dados = await pool.chamar(
            projeto.id,
            "chat.carregar_anteriores",
            {
                "conversa_id": conversa_id,
                "antes_de_seq": antes if antes is not None else 10**9,
                "limite": limite,
            },
        )
    except ErroServidor as exc:
        if exc.codigo.endswith("NU-002"):
            return {"itens": [], "proximo": None}
        raise
    itens = dados.get("mensagens") or dados.get("itens") or []
    return {"itens": itens, "proximo": dados.get("proximo")}


@router.post("/{projeto_id}/mensagens", status_code=202)
async def enviar_mensagem(
    projeto_id: str,
    corpo: modelos.MensagemNova,
    tarefas: BackgroundTasks,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado in {"importando", "indexando"}:
        raise ErroServidor(
            "SV-241",
            "Espere a importação terminar para conversar sobre o projeto.",
            status_http=409,
        )
    pool = _exigir_pool(estado)
    raiz = _raiz(estado, projeto.id)
    hub = estado.hub
    req_id = uuid.uuid4().hex
    texto = corpo.texto.strip()
    conversa_id = _conversa_do_projeto(con, projeto.id)
    banco = estado.banco

    async def _rodar() -> None:
        if True:  # mantém o bloco do turno indentado como estava
            pass
        async def _turno() -> None:
            nao_local = None
            try:
                worker = await pool.obter(projeto.id)
                conversa = conversa_id
                if not conversa:
                    criada = await worker.chamar(
                        "chat.criar_conversa",
                        {"workspace": str(raiz), "title": projeto.nome},
                    )
                    conversa = criada.get("conversation_id") or criada.get("id")
                    if conversa:
                        con_local = banco.conectar()
                        try:
                            _guardar_conversa(con_local, projeto.id, conversa)
                        finally:
                            con_local.close()

                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="mensagem.criada",
                    dados={"mensagem": {"papel": "usuario", "texto": texto}},
                    req_id=req_id,
                )

                async def ao_evento(mensagem: dict) -> None:
                    _emitir(
                        raiz=raiz,
                        hub=hub,
                        projeto_id=projeto.id,
                        evento=mensagem.get("evento", "aviso"),
                        dados=mensagem.get("dados") or {},
                        req_id=req_id,
                        job_id=(mensagem.get("dados") or {}).get("job_id"),
                        origem="nucleo",
                    )

                await pool.chamar(
                    projeto.id,
                    "chat.enviar",
                    {"conversa_id": conversa, "texto": texto},
                    ao_evento=ao_evento,
                )
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="nucleo.res",
                    dados={"req_id": req_id, "ok": True},
                    req_id=req_id,
                )
            except ErroServidor as exc:
                nao_local = exc
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="nucleo.res",
                    dados={
                        "req_id": req_id,
                        "ok": False,
                        "erro": {"codigo": exc.codigo, "mensagem": exc.mensagem},
                    },
                    req_id=req_id,
                )
            except Exception as exc:  # pragma: no cover - defensivo
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="nucleo.res",
                    dados={
                        "req_id": req_id,
                        "ok": False,
                        "erro": {"codigo": "SV-099", "mensagem": type(exc).__name__},
                    },
                    req_id=req_id,
                )

        await _turno()

    tarefas.add_task(_rodar)
    return {"req_id": req_id}


@router.post("/{projeto_id}/cancelar", status_code=202)
async def cancelar(
    projeto_id: str,
    corpo: modelos.Cancelamento,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    pool = _exigir_pool(estado)

    worker = await pool.obter(projeto.id)
    await worker.cancelar(corpo.req_id)
    return {"cancelado": corpo.req_id}
