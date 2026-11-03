"""Sessões por cookie e CSRF (W-11 §Sessão e CSRF).

- token de 32 bytes em `secrets.token_urlsafe`; o banco guarda só o **sha256**;
- validade deslizante de 30 dias, teto de 90 dias desde a criação;
- `csrf` por sessão, devolvido em `GET /auth/eu` e exigido em `X-MF-CSRF`;
- conta bloqueada (`ativo=0`) invalida as sessões na hora.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

NOME_COOKIE = "mf_sessao"
DIAS_DESLIZANTE = 30
DIAS_TETO = 90
AGENTE_MAX = 120


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def prefixo_ip(ip: str | None) -> str | None:
    """`/24` para IPv4 e `/48` para IPv6 — o suficiente para auditoria."""
    if not ip:
        return None
    if ":" in ip:
        partes = ip.split(":")
        return ":".join(partes[:3]) + "::/48"
    partes = ip.split(".")
    if len(partes) < 3:
        return None
    return ".".join(partes[:3]) + ".0/24"


@dataclass(frozen=True)
class Sessao:
    id_hash: str
    usuario_id: str
    csrf: str
    criada_em: str
    expira_em: str

    def expirada(self, quando: datetime | None = None) -> bool:
        referencia = quando or agora()
        return datetime.strptime(self.expira_em, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        ) <= referencia


def criar(
    con: sqlite3.Connection,
    *,
    usuario_id: str,
    ip: str | None = None,
    agente: str | None = None,
) -> tuple[str, Sessao]:
    """Cria a sessão e devolve `(token_em_claro, sessao)`. O token só existe aqui."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    criada = agora()
    sessao = Sessao(
        id_hash=_hash(token),
        usuario_id=usuario_id,
        csrf=csrf,
        criada_em=iso(criada),
        expira_em=iso(criada + timedelta(days=DIAS_DESLIZANTE)),
    )
    con.execute(
        "INSERT INTO sessoes (id_hash, usuario_id, csrf, criada_em, expira_em, ip_prefixo, agente)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            sessao.id_hash,
            sessao.usuario_id,
            sessao.csrf,
            sessao.criada_em,
            sessao.expira_em,
            prefixo_ip(ip),
            (agente or "")[:AGENTE_MAX] or None,
        ),
    )
    return token, sessao


def obter(con: sqlite3.Connection, token: str | None) -> Sessao | None:
    if not token:
        return None
    linha = con.execute(
        "SELECT id_hash, usuario_id, csrf, criada_em, expira_em FROM sessoes WHERE id_hash = ?",
        (_hash(token),),
    ).fetchone()
    if linha is None:
        return None
    sessao = Sessao(
        id_hash=linha["id_hash"],
        usuario_id=linha["usuario_id"],
        csrf=linha["csrf"],
        criada_em=linha["criada_em"],
        expira_em=linha["expira_em"],
    )
    if sessao.expirada():
        apagar(con, sessao.id_hash)
        return None
    return sessao


def renovar(con: sqlite3.Connection, sessao: Sessao) -> Sessao:
    """Desliza a validade, respeitando o teto de 90 dias desde a criação."""
    criada = datetime.strptime(sessao.criada_em, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    novo = min(agora() + timedelta(days=DIAS_DESLIZANTE), criada + timedelta(days=DIAS_TETO))
    if iso(novo) == sessao.expira_em:
        return sessao
    con.execute(
        "UPDATE sessoes SET expira_em = ? WHERE id_hash = ?", (iso(novo), sessao.id_hash)
    )
    return Sessao(
        id_hash=sessao.id_hash,
        usuario_id=sessao.usuario_id,
        csrf=sessao.csrf,
        criada_em=sessao.criada_em,
        expira_em=iso(novo),
    )


def apagar(con: sqlite3.Connection, id_hash: str) -> None:
    con.execute("DELETE FROM sessoes WHERE id_hash = ?", (id_hash,))


def apagar_do_usuario(con: sqlite3.Connection, usuario_id: str) -> int:
    cur = con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
    return cur.rowcount or 0


def limpar_expiradas(con: sqlite3.Connection) -> int:
    cur = con.execute("DELETE FROM sessoes WHERE expira_em <= ?", (iso(agora()),))
    return cur.rowcount or 0


def csrf_confere(sessao: Sessao, enviado: str | None) -> bool:
    if not enviado:
        return False
    return secrets.compare_digest(sessao.csrf, enviado.strip())
