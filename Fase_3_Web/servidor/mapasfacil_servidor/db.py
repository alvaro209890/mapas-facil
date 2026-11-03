"""Banco do servidor — SQLite com migração versionada (W-03/W-11).

Um arquivo só, sem ORM: o volume é pequeno e SQL explícito é mais fácil de auditar
do que um mapeamento implícito. Toda conexão aplica `PRAGMA foreign_keys=ON` e
`journal_mode=WAL` (leitura concorrente com o escritor).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

MIGRACOES_DIR = Path(__file__).resolve().parent / "migracoes"
MIGRACAO_INICIAL = "0001_inicial.sql"


@dataclass(frozen=True)
class Banco:
    caminho: Path

    def conectar(self) -> sqlite3.Connection:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        # `check_same_thread=False`: rota `async def` roda a dependência síncrona
        # em outro thread; a conexão é usada dentro de uma requisição só, então
        # não há concorrência real sobre ela.
        con = sqlite3.connect(
            self.caminho, isolation_level=None, timeout=30.0, check_same_thread=False
        )
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA busy_timeout = 10000")
        return con

    def migrar(self) -> int:
        """Aplica as migrações pendentes e devolve a versão final do schema."""
        con = self.conectar()
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                " versao INTEGER PRIMARY KEY, aplicada_em TEXT NOT NULL)"
            )
            atual = con.execute(
                "SELECT COALESCE(MAX(versao), 0) FROM schema_version"
            ).fetchone()[0]
            for arquivo in sorted(MIGRACOES_DIR.glob("*.sql")):
                try:
                    versao = int(arquivo.name.split("_", 1)[0])
                except ValueError:  # pragma: no cover - nome fora do padrão
                    continue
                if versao <= atual:
                    continue
                script = arquivo.read_text(encoding="utf-8")
                con.executescript(script)
                con.execute(
                    "INSERT INTO schema_version (versao, aplicada_em) VALUES (?, datetime('now'))",
                    (versao,),
                )
                atual = versao
            return int(atual)
        finally:
            con.close()

    def versao(self) -> int:
        con = self.conectar()
        try:
            linha = con.execute(
                "SELECT COALESCE(MAX(versao), 0) FROM schema_version"
            ).fetchone()
            return int(linha[0]) if linha else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            con.close()

    def sessao(self) -> Iterator[sqlite3.Connection]:
        con = self.conectar()
        try:
            yield con
        finally:
            con.close()
