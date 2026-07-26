# Repositório SQLite de contas locais (F1-14 / M5).

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.contas import banco as contas_banco
from mapasfacil_nucleo.protocolo import novo_id


def agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class RepositorioContas:
    def __init__(self, diretorio: Path | None = None) -> None:
        self._diretorio = diretorio or contas_banco.diretorio_contas()
        self._conn = contas_banco.conectar(contas_banco.caminho_banco(self._diretorio))

    @property
    def caminho(self) -> Path:
        return contas_banco.caminho_banco(self._diretorio)

    def fechar(self) -> None:
        self._conn.close()

    def buscar_por_email(self, email: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM contas WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        return dict(row) if row else None

    def buscar_por_id(self, conta_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone()
        return dict(row) if row else None

    def inserir_conta(
        self,
        *,
        email: str,
        senha_hash: str,
        nome: str | None,
    ) -> dict[str, Any]:
        conta_id = novo_id()
        agora = agora_iso()
        self._conn.execute(
            """
            INSERT INTO contas (id, email, nome, senha_hash, criado_em, ultimo_login_em, ativa)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (conta_id, email, nome, senha_hash, agora, agora),
        )
        return {
            "id": conta_id,
            "email": email,
            "nome": nome,
            "criado_em": agora,
        }

    def marcar_login(self, conta_id: str) -> None:
        self._conn.execute(
            "UPDATE contas SET ultimo_login_em = ? WHERE id = ?",
            (agora_iso(), conta_id),
        )

    def criar_sessao_local(
        self,
        conta_id: str,
        *,
        lembrar_neste_pc: bool = True,
        expira_em: str | None = None,
    ) -> dict[str, Any]:
        # Uma sessão ativa por instalação: apaga as anteriores.
        self._conn.execute("DELETE FROM sessoes_locais")
        sessao_id = novo_id()
        agora = agora_iso()
        self._conn.execute(
            """
            INSERT INTO sessoes_locais (id, conta_id, criada_em, expira_em, lembrar_neste_pc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sessao_id, conta_id, agora, expira_em, 1 if lembrar_neste_pc else 0),
        )
        return {
            "id": sessao_id,
            "conta_id": conta_id,
            "criada_em": agora,
            "expira_em": expira_em,
            "lembrar_neste_pc": lembrar_neste_pc,
        }

    def sessao_lembrada(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT s.*, c.email, c.nome, c.ativa
            FROM sessoes_locais s
            JOIN contas c ON c.id = s.conta_id
            WHERE s.lembrar_neste_pc = 1
            ORDER BY s.criada_em DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        dados = dict(row)
        if not dados.get("ativa"):
            return None
        expira = dados.get("expira_em")
        if isinstance(expira, str) and expira and expira < agora_iso():
            self._conn.execute("DELETE FROM sessoes_locais WHERE id = ?", (dados["id"],))
            return None
        return dados

    def limpar_sessoes(self) -> None:
        self._conn.execute("DELETE FROM sessoes_locais")

    def apagar_tudo(self) -> None:
        """‘Sair e esquecer este PC’: zera contas e sessões neste banco."""
        self._conn.execute("DELETE FROM sessoes_locais")
        self._conn.execute("DELETE FROM contas")

    def conta_publica(self, row: dict[str, Any] | sqlite3.Row) -> dict[str, Any]:
        dados = dict(row)
        return {
            "id": dados["id"],
            "email": dados["email"],
            "nome": dados.get("nome"),
        }
