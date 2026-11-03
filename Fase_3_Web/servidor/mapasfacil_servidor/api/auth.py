"""Rotas de autenticação e conta (W-03 §Autenticação)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from ..auth import contas, limitador as limitador_mod, senhas, sessoes
from ..erros import ErroServidor
from . import deps, modelos

router = APIRouter(prefix="/auth", tags=["auth"])

_SSO_MAX_AGE = sessoes.DIAS_TETO * 24 * 3600


def _definir_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        sessoes.NOME_COOKIE,
        token,
        max_age=_SSO_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _usuario_publico(usuario: contas.Usuario) -> dict:
    return usuario.publico()


@router.post("/cadastrar", status_code=201)
def cadastrar(
    corpo: modelos.Cadastro,
    request: Request,
    response: Response,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    usuario = contas.criar(
        con,
        nome=corpo.nome,
        email=corpo.email,
        senha=corpo.senha,
        admin_email=estado.admin_email,
    )
    token, _ = sessoes.criar(
        con,
        usuario_id=usuario.id,
        ip=deps.ip_do_pedido(request),
        agente=request.headers.get("user-agent"),
    )
    _definir_cookie(response, token)
    return {"usuario": _usuario_publico(usuario)}


@router.post("/entrar")
def entrar(
    corpo: modelos.Entrada,
    request: Request,
    response: Response,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    assert estado.limitador is not None
    ip = deps.ip_do_pedido(request)
    chave = limitador_mod.chave(corpo.email, ip)
    if estado.limitador.bloqueado(chave):
        espera = estado.limitador.segundos_para_liberar(chave)
        raise ErroServidor(
            "SV-005",
            "Muitas tentativas de login. Espere alguns minutos.",
            status_http=429,
            porque="Cinco falhas em quinze minutos bloqueiam a origem por um tempo.",
            o_que_fazer=f"Tente de novo em {max(1, espera // 60)} min.",
            detalhes={"espera_s": espera},
        )
    try:
        usuario = contas.autenticar(con, email=corpo.email, senha=corpo.senha)
    except ErroServidor as exc:
        if exc.codigo == "SV-001":
            estado.limitador.registrar_falha(chave)
        raise
    estado.limitador.registrar_sucesso(chave)
    token, _ = sessoes.criar(
        con,
        usuario_id=usuario.id,
        ip=ip,
        agente=request.headers.get("user-agent"),
    )
    _definir_cookie(response, token)
    return {"usuario": _usuario_publico(usuario)}


@router.post("/sair", status_code=204)
def sair(
    response: Response,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    sessao: sessoes.Sessao = Depends(deps.pegar_sessao),
) -> Response:
    sessoes.apagar(con, sessao.id_hash)
    contas.auditar(con, acao="saiu", usuario_id=sessao.usuario_id)
    response.delete_cookie(sessoes.NOME_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/eu")
def eu(usuario: contas.Usuario = Depends(deps.pegar_usuario), request: Request = None) -> dict:  # type: ignore[assignment]
    sessao = getattr(request.state, "sessao", None) if request is not None else None
    return {"usuario": _usuario_publico(usuario), "csrf": sessao.csrf if sessao else None}


@router.post("/senha", status_code=204)
def trocar_senha(
    corpo: modelos.TrocaSenha,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> Response:
    motivo = senhas.problemas(corpo.senha_nova)
    if motivo:
        raise ErroServidor("SV-010", motivo, status_http=400)
    contas.trocar_senha(
        con,
        usuario_id=usuario.id,
        senha_atual=corpo.senha_atual,
        senha_nova=corpo.senha_nova,
    )
    return Response(status_code=204)
