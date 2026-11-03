"""Rotas de administração (papel `admin`) — W-03 §Administração."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from ..auth import contas, sessoes
from ..erros import ErroServidor
from . import deps, modelos

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usuarios")
def listar_usuarios(
    con: sqlite3.Connection = Depends(deps.pegar_con),
    _admin: contas.Usuario = Depends(deps.exigir_admin),
) -> dict:
    return {"itens": [u.publico() for u in contas.listar(con)]}


@router.post("/usuarios", status_code=201)
def criar_usuario(
    corpo: modelos.UsuarioNovoAdmin,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    admin: contas.Usuario = Depends(deps.exigir_admin),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    temporaria = contas.senhas.gerar_senha_temporaria()
    usuario = contas.criar(
        con,
        nome=corpo.nome,
        email=corpo.email,
        senha=temporaria,
        papel=corpo.papel,
        trocar_senha=True,
    )
    contas.auditar(con, acao="criou_usuario", usuario_id=admin.id, alvo=usuario.id)
    # A senha temporária aparece **uma vez** e não é gravada em claro em lugar nenhum.
    return {"usuario": usuario.publico(), "senha_temporaria": temporaria}


@router.patch("/usuarios/{usuario_id}")
def atualizar_usuario(
    usuario_id: str,
    corpo: modelos.UsuarioPatchAdmin,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    admin: contas.Usuario = Depends(deps.exigir_admin),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    resposta: dict = {}
    if corpo.ativo is not None:
        usuario = contas.bloquear(
            con, usuario_id=usuario_id, ativo=corpo.ativo, autor_id=admin.id
        )
        resposta["usuario"] = usuario.publico()
    if corpo.papel is not None:
        usuario = contas.definir_papel(
            con, usuario_id=usuario_id, papel=corpo.papel, autor_id=admin.id
        )
        resposta["usuario"] = usuario.publico()
    if corpo.redefinir_senha:
        resposta["senha_temporaria"] = contas.redefinir_senha(
            con, usuario_id=usuario_id, autor_id=admin.id
        )
    if not resposta:
        raise ErroServidor(
            "SV-016",
            "Nada para atualizar.",
            status_http=400,
            detalhes={"campos": ["ativo", "papel", "redefinir_senha"]},
        )
    if "usuario" not in resposta:
        usuario = contas.buscar(con, usuario_id)
        if usuario is None:
            raise ErroServidor("SV-034", "Usuário não encontrado.", status_http=404)
        resposta["usuario"] = usuario.publico()
    return resposta


@router.get("/auditoria")
def auditoria(
    antes: int | None = Query(default=None, ge=1),
    limite: int = Query(default=50, ge=1, le=200),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    _admin: contas.Usuario = Depends(deps.exigir_admin),
) -> dict:
    sql = "SELECT * FROM auditoria"
    params: list[object] = []
    if antes:
        sql += " WHERE id < ?"
        params.append(antes)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limite + 1)
    linhas = con.execute(sql, params).fetchall()
    itens = [
        {
            "id": linha["id"],
            "em": linha["em"],
            "usuario_id": linha["usuario_id"],
            "acao": linha["acao"],
            "alvo": linha["alvo"],
            "detalhe": json.loads(linha["detalhe"]) if linha["detalhe"] else None,
        }
        for linha in linhas[:limite]
    ]
    proximo = linhas[limite]["id"] if len(linhas) > limite else None
    return {"itens": itens, "proximo": proximo}


@router.get("/saude")
def saude(
    estado: deps.AppState = Depends(deps.pegar_estado),
    _admin: contas.Usuario = Depends(deps.exigir_admin),
) -> dict:
    """Workers, vagas, disco e versão do núcleo — sem dado de usuário."""
    raiz = Path(str(getattr(estado.config, "raiz", ".")))
    try:
        livre = shutil.disk_usage(raiz).free / (1024**3)
    except OSError:  # pragma: no cover - disco sempre existe
        livre = None
    pool = getattr(estado, "pool", None)
    return {
        "workers": pool.estado() if pool is not None else {"workers": 0},
        "vagas_livres": getattr(estado, "vagas_livres", None),
        "disco_livre_gb": round(livre, 1) if livre is not None else None,
        "schema": estado.banco.versao(),
        "nucleo": getattr(estado, "nucleo", None),
    }
