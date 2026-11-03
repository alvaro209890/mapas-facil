"""Dependências da API: conexão, sessão, permissão e CSRF (W-03/W-11).

O estado global do app (`AppState`) é montado no `create_app` e injetado por
dependência — é o que deixa os testes usarem banco em `tmp_path` sem variável de
ambiente nenhuma.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterator

from fastapi import Depends, Request

from ..auth import contas, limitador, sessoes
from ..db import Banco
from ..erros import ErroServidor
from ..eventos.sse import Hub


@dataclass
class AppState:
    banco: Banco
    admin_email: str | None = None
    limitador: limitador.Limitador | None = None
    config: object | None = None
    hub: Hub = field(default_factory=Hub)

    def __post_init__(self) -> None:
        if self.limitador is None:
            self.limitador = limitador.Limitador()


def pegar_estado(request: Request) -> AppState:
    estado = getattr(request.app.state, "mf", None)
    if estado is None:  # pragma: no cover - só se o app foi montado errado
        raise ErroServidor("SV-000", "Estado do app não inicializado.", status_http=500)
    return estado


def pegar_con(estado: AppState = Depends(pegar_estado)) -> Iterator[sqlite3.Connection]:
    con = estado.banco.conectar()
    try:
        yield con
    finally:
        con.close()


def ip_do_pedido(request: Request) -> str | None:
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip() or None
    return request.client.host if request.client else None


def pegar_sessao(
    request: Request,
    con: sqlite3.Connection = Depends(pegar_con),
) -> sessoes.Sessao:
    token = request.cookies.get(sessoes.NOME_COOKIE)
    sessao = sessoes.obter(con, token)
    if sessao is None:
        raise ErroServidor(
            "SV-002",
            "Sem sessão válida.",
            status_http=401,
            o_que_fazer="Entre de novo em /entrar.",
        )
    renovada = sessoes.renovar(con, sessao)
    request.state.sessao = renovada
    return renovada


def pegar_usuario(
    con: sqlite3.Connection = Depends(pegar_con),
    sessao: sessoes.Sessao = Depends(pegar_sessao),
) -> contas.Usuario:
    usuario = contas.buscar(con, sessao.usuario_id)
    if usuario is None:
        raise ErroServidor("SV-002", "Sessão órfã.", status_http=401)
    if not usuario.ativo:
        sessoes.apagar_do_usuario(con, usuario.id)
        raise ErroServidor(
            "SV-003",
            "Esta conta está bloqueada.",
            status_http=403,
            o_que_fazer="Fale com o administrador do Mapas Fácil.",
        )
    return usuario


def exigir_admin(usuario: contas.Usuario = Depends(pegar_usuario)) -> contas.Usuario:
    if usuario.papel != "admin":
        raise ErroServidor(
            "SV-030",
            "Ação restrita ao administrador.",
            status_http=403,
            porque="O papel desta conta é 'usuario'.",
        )
    return usuario


def _origem_estranha(request: Request) -> bool:
    origem = request.headers.get("origin")
    if origem is None:
        return False  # cliente sem Origin (curl/teste) não é CSRF
    permitidas = {str(getattr(request.app.state, "mf_origem", "") or "")}
    return origem.rstrip("/") not in permitidas


def exigir_csrf(
    request: Request,
    sessao: sessoes.Sessao = Depends(pegar_sessao),
) -> sessoes.Sessao:
    """Mutação sem `X-MF-CSRF` correto → `403 SV-020`; Origin estranho idem."""
    if _origem_estranha(request):
        raise ErroServidor(
            "SV-021",
            "Origem não permitida.",
            status_http=403,
            porque="Requisição de outro site não pode mudar dado por cookie de sessão.",
        )
    enviado = request.headers.get("x-mf-csrf")
    if not sessoes.csrf_confere(sessao, enviado):
        raise ErroServidor(
            "SV-020",
            "Token CSRF ausente ou inválido.",
            status_http=403,
            o_que_fazer="Recarregue a página: o token vem de GET /auth/eu.",
        )
    return sessao
