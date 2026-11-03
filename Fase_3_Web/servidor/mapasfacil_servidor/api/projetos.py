"""Rotas de projetos (W-03 §Projetos)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, Response

from .. import projetos_repo
from ..auth import contas, sessoes
from ..erros import ErroServidor
from . import deps, modelos

router = APIRouter(prefix="/projetos", tags=["projetos"])


def _admin(usuario: contas.Usuario) -> bool:
    return usuario.papel == "admin"


@router.get("")
def listar(
    busca: str | None = Query(default=None, max_length=120),
    estado: str | None = Query(default=None, max_length=30),
    antes: str | None = Query(default=None, max_length=64),
    limite: int = Query(default=50, ge=1, le=200),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    return projetos_repo.listar(
        con,
        usuario_id=usuario.id,
        admin=_admin(usuario),
        busca=busca,
        estado=estado,
        antes=antes,
        limite=limite,
    )


@router.post("", status_code=201)
def criar(
    corpo: modelos.ProjetoNovo,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    projeto = projetos_repo.criar(
        con,
        usuario_id=usuario.id,
        nome=corpo.nome,
        folha=corpo.folha.model_dump(),
    )
    contas.auditar(con, acao="criou_projeto", usuario_id=usuario.id, alvo=projeto.id)
    return {"projeto": projeto.completo()}


@router.get("/{projeto_id}")
def detalhar(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    return {
        "projeto": projeto.completo(),
        "versoes": projetos_repo.versoes(con, projeto.id),
    }


@router.patch("/{projeto_id}")
async def renomear(
    projeto_id: str,
    corpo: modelos.ProjetoPatch,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if corpo.nome is not None:
        projeto = projetos_repo.renomear(con, projeto, corpo.nome)
        # W5-11: o título da conversa acompanha o nome do projeto.
        conversa_id = con.execute(
            "SELECT conversa_id FROM projetos WHERE id = ?", (projeto.id,)
        ).fetchone()["conversa_id"]
        pool = getattr(estado, "pool", None)
        if conversa_id and pool is not None:
            from ..erros import ErroServidor

            try:
                await pool.chamar(
                    projeto.id,
                    "chat.renomear",
                    {"conversa_id": conversa_id, "title": projeto.nome},
                )
            except ErroServidor:
                # Renomear o projeto não pode falhar porque a conversa não renomeou.
                pass
    return {"projeto": projeto.completo()}


@router.delete("/{projeto_id}", status_code=204)
def apagar(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> Response:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado == "gerando":
        raise ErroServidor(
            "SV-094",
            "Não apague um projeto enquanto ele gera.",
            status_http=409,
            o_que_fazer="Espere a geração terminar ou cancele.",
        )
    projetos_repo.transicionar(con, projeto, "lixeira")
    contas.auditar(con, acao="apagou_projeto", usuario_id=usuario.id, alvo=projeto.id)
    return Response(status_code=204)


@router.post("/{projeto_id}/restaurar")
def restaurar(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado != "lixeira":
        raise ErroServidor(
            "SV-090",
            "Este projeto não está na lixeira.",
            status_http=409,
        )
    destino = "pronto" if projeto.versao_atual > 0 else "aguardando_zip"
    projeto = projetos_repo.transicionar(con, projeto, destino)
    return {"projeto": projeto.completo()}


@router.get("/{projeto_id}/versoes")
def versoes(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    return {"itens": projetos_repo.versoes(con, projeto.id)}
