"""Contas: criar, autenticar, bloquear, redefinir (W-11 §Contas)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass

from ..erros import ErroServidor
from . import sessoes, senhas


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    nome: str
    papel: str
    trocar_senha: bool
    ativo: bool
    criado_em: str
    ultimo_acesso: str | None

    def publico(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "nome": self.nome,
            "papel": self.papel,
            "trocar_senha": self.trocar_senha,
            "ativo": self.ativo,
            "criado_em": self.criado_em,
            "ultimo_acesso": self.ultimo_acesso,
        }


def _de_linha(linha: sqlite3.Row) -> Usuario:
    return Usuario(
        id=linha["id"],
        email=linha["email"],
        nome=linha["nome"],
        papel=linha["papel"],
        trocar_senha=bool(linha["trocar_senha"]),
        ativo=bool(linha["ativo"]),
        criado_em=linha["criado_em"],
        ultimo_acesso=linha["ultimo_acesso"],
    )


def auditar(
    con: sqlite3.Connection,
    *,
    acao: str,
    usuario_id: str | None = None,
    alvo: str | None = None,
    detalhe: dict | None = None,
) -> None:
    """Grava auditoria. `detalhe` nunca leva senha, hash nem CPF."""
    con.execute(
        "INSERT INTO auditoria (em, usuario_id, acao, alvo, detalhe) VALUES (?,?,?,?,?)",
        (
            sessoes.iso(sessoes.agora()),
            usuario_id,
            acao,
            alvo,
            json.dumps(detalhe, ensure_ascii=False) if detalhe else None,
        ),
    )


def buscar_por_email(con: sqlite3.Connection, email: str) -> Usuario | None:
    linha = con.execute(
        "SELECT * FROM usuarios WHERE email = ?", (senhas.normalizar_email(email),)
    ).fetchone()
    return _de_linha(linha) if linha else None


def buscar(con: sqlite3.Connection, usuario_id: str) -> Usuario | None:
    linha = con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    return _de_linha(linha) if linha else None


def listar(con: sqlite3.Connection) -> list[Usuario]:
    linhas = con.execute("SELECT * FROM usuarios ORDER BY criado_em DESC").fetchall()
    return [_de_linha(linha) for linha in linhas]


def criar(
    con: sqlite3.Connection,
    *,
    nome: str,
    email: str,
    senha: str,
    papel: str = "usuario",
    trocar_senha: bool = False,
    admin_email: str | None = None,
) -> Usuario:
    """Cria conta. Cadastro aberto (D27); o primeiro admin vem de `MF_ADMIN_EMAIL`."""
    nome = (nome or "").strip()
    email_norm = senhas.normalizar_email(email or "")
    if not nome or len(nome) > 120:
        raise ErroServidor(
            "SV-014",
            "Informe o nome (até 120 caracteres).",
            status_http=400,
            o_que_fazer="Preencha o nome completo.",
        )
    if not senhas.conferir_email(email_norm):
        raise ErroServidor(
            "SV-013",
            "E-mail inválido.",
            status_http=400,
            o_que_fazer="Confira o endereço: precisa ter o formato nome@dominio.com.",
        )
    motivo = senhas.problemas(senha or "")
    if motivo:
        raise ErroServidor(
            "SV-010",
            motivo,
            status_http=400,
            o_que_fazer="Escolha uma senha longa e que você não use em outro site.",
        )
    if buscar_por_email(con, email_norm) is not None:
        raise ErroServidor(
            "SV-012",
            "Este e-mail já tem conta.",
            status_http=409,
            o_que_fazer="Entre com a senha que você já usa — ou peça redefinição ao admin.",
        )

    if papel not in {"usuario", "admin"}:
        raise ErroServidor("SV-015", "Papel inválido.", status_http=400)

    if (
        papel == "usuario"
        and admin_email
        and senhas.normalizar_email(admin_email) == email_norm
    ):
        papel = "admin"

    usuario_id = uuid.uuid4().hex
    criado = sessoes.iso(sessoes.agora())
    con.execute(
        "INSERT INTO usuarios (id, email, nome, papel, senha_hash, trocar_senha, ativo, criado_em)"
        " VALUES (?,?,?,?,?,?,1,?)",
        (
            usuario_id,
            email_norm,
            nome,
            papel,
            senhas.gerar_hash(senha),
            1 if trocar_senha else 0,
            criado,
        ),
    )
    auditar(con, acao="cadastrou", usuario_id=usuario_id, alvo=usuario_id)
    criado_usuario = buscar(con, usuario_id)
    assert criado_usuario is not None
    return criado_usuario


def autenticar(con: sqlite3.Connection, *, email: str, senha: str) -> Usuario:
    """Confere credencial. Erro igual para e-mail inexistente e senha errada."""
    usuario = buscar_por_email(con, email)
    if usuario is None:
        # Custo constante: deriva um hash descartável para não vazar existência por tempo.
        senhas.conferir(senha, senhas.gerar_hash("senha-inexistente"))
        auditar(con, acao="falhou_login", detalhe={"email": senhas.normalizar_email(email)})
        raise ErroServidor(
            "SV-001",
            "E-mail ou senha não conferem.",
            status_http=401,
            o_que_fazer="Confira os dois campos; se esquecer a senha, peça redefinição.",
        )
    if not senhas.conferir(senha, _hash_de(con, usuario.id)):
        auditar(con, acao="falhou_login", usuario_id=usuario.id)
        raise ErroServidor(
            "SV-001",
            "E-mail ou senha não conferem.",
            status_http=401,
            o_que_fazer="Confira os dois campos; se esquecer a senha, peça redefinição.",
        )
    if not usuario.ativo:
        auditar(con, acao="falhou_login", usuario_id=usuario.id, detalhe={"motivo": "bloqueado"})
        raise ErroServidor(
            "SV-003",
            "Esta conta está bloqueada.",
            status_http=403,
            porque="Só o administrador pode reativar uma conta bloqueada.",
            o_que_fazer="Fale com o administrador do Mapas Fácil.",
        )
    momento = sessoes.iso(sessoes.agora())
    con.execute("UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?", (momento, usuario.id))
    auditar(con, acao="entrou", usuario_id=usuario.id)
    atualizado = buscar(con, usuario.id)
    assert atualizado is not None
    return atualizado


def _hash_de(con: sqlite3.Connection, usuario_id: str) -> str:
    linha = con.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    return linha["senha_hash"] if linha else ""


def trocar_senha(
    con: sqlite3.Connection,
    *,
    usuario_id: str,
    senha_atual: str,
    senha_nova: str,
) -> None:
    if not senhas.conferir(senha_atual, _hash_de(con, usuario_id)):
        raise ErroServidor(
            "SV-001",
            "A senha atual não confere.",
            status_http=401,
            o_que_fazer="Digite a senha com que você entrou.",
        )
    motivo = senhas.problemas(senha_nova or "")
    if motivo:
        raise ErroServidor("SV-010", motivo, status_http=400)
    con.execute(
        "UPDATE usuarios SET senha_hash = ?, trocar_senha = 0 WHERE id = ?",
        (senhas.gerar_hash(senha_nova), usuario_id),
    )
    auditar(con, acao="trocou_senha", usuario_id=usuario_id)


def bloquear(con: sqlite3.Connection, *, usuario_id: str, ativo: bool, autor_id: str | None) -> Usuario:
    usuario = buscar(con, usuario_id)
    if usuario is None:
        raise ErroServidor("SV-034", "Usuário não encontrado.", status_http=404)
    con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (1 if ativo else 0, usuario_id))
    if not ativo:
        # Bloqueio derruba as sessões na hora (W-03 §Admin).
        sessoes.apagar_do_usuario(con, usuario_id)
    auditar(
        con,
        acao="desbloqueou" if ativo else "bloqueou",
        usuario_id=autor_id,
        alvo=usuario_id,
    )
    atualizado = buscar(con, usuario_id)
    assert atualizado is not None
    return atualizado


def redefinir_senha(
    con: sqlite3.Connection, *, usuario_id: str, autor_id: str | None
) -> str:
    """Define senha temporária e devolve o valor em claro **uma única vez**."""
    usuario = buscar(con, usuario_id)
    if usuario is None:
        raise ErroServidor("SV-034", "Usuário não encontrado.", status_http=404)
    temporaria = senhas.gerar_senha_temporaria()
    con.execute(
        "UPDATE usuarios SET senha_hash = ?, trocar_senha = 1 WHERE id = ?",
        (senhas.gerar_hash(temporaria), usuario_id),
    )
    sessoes.apagar_do_usuario(con, usuario_id)
    auditar(con, acao="redefiniu_senha", usuario_id=autor_id, alvo=usuario_id)
    return temporaria


def definir_papel(
    con: sqlite3.Connection, *, usuario_id: str, papel: str, autor_id: str | None
) -> Usuario:
    if papel not in {"usuario", "admin"}:
        raise ErroServidor("SV-015", "Papel inválido.", status_http=400)
    usuario = buscar(con, usuario_id)
    if usuario is None:
        raise ErroServidor("SV-034", "Usuário não encontrado.", status_http=404)
    con.execute("UPDATE usuarios SET papel = ? WHERE id = ?", (papel, usuario_id))
    auditar(con, acao="mudou_papel", usuario_id=autor_id, alvo=usuario_id, detalhe={"papel": papel})
    atualizado = buscar(con, usuario_id)
    assert atualizado is not None
    return atualizado
