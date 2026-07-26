# F1-17 §Layout em disco / §Migrações — onde o banco mora, como abre e como migra.
#
# Banco ÚNICO global (D13): `%APPDATA%\MapasFacil\chats\chats.sqlite`. Não é um
# banco por projeto — a sidebar precisa listar conversas de todos os workspaces, e
# `workspace_fingerprint` por conversa dá o filtro por pasta de graça.
#
# `%APPDATA%\MapasFacil\` não é workspace (F1-01 §fsguard): o acesso passa por
# aqui, restrito a essa árvore, sem allowlist dinâmica. Nada de rede neste pacote.

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

from mapasfacil_nucleo.erros import ErroNucleo

PASTA_CONVERSAS = "conversas"

_MIGRACOES = Path(__file__).resolve().parent / "migracoes"
_PADRAO_MIGRACAO = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def pasta_dados() -> Path:
    """Raiz de `%APPDATA%\\MapasFacil\\` (ou equivalente fora do Windows).

    `MAPASFACIL_APPDATA` vence sempre — é como o processo main do Electron passa
    `app.getPath("userData")` ao sidecar, e como os testes apontam para `tmp_path`.
    """
    explicito = os.environ.get("MAPASFACIL_APPDATA")
    if explicito:
        return Path(explicito)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "MapasFacil"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "MapasFacil"


def pasta_chats() -> Path:
    return pasta_dados() / "chats"


def caminho_banco() -> Path:
    return pasta_chats() / "chats.sqlite"


def pasta_anexos(conversation_id: str | None = None) -> Path:
    raiz = pasta_chats() / "anexos"
    return raiz if conversation_id is None else raiz / conversation_id


def _migracoes_disponiveis() -> list[tuple[int, Path]]:
    encontradas: list[tuple[int, Path]] = []
    for arquivo in sorted(_MIGRACOES.glob("*.sql")):
        casa = _PADRAO_MIGRACAO.match(arquivo.name)
        if casa is None:
            raise ErroNucleo(
                "NU-241",
                f"Nome de migração fora do padrão 00N_nome.sql: {arquivo.name}",
                {"arquivo": arquivo.name},
            )
        encontradas.append((int(casa.group(1)), arquivo))
    if not encontradas:
        raise ErroNucleo("NU-241", "Nenhuma migração encontrada em conversas/migracoes/.")
    return encontradas


def versao_atual(conexao: sqlite3.Connection) -> int:
    tem_tabela = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_versao'"
    ).fetchone()
    if tem_tabela is None:
        return 0
    linha = conexao.execute("SELECT MAX(versao) FROM schema_versao").fetchone()
    return int(linha[0]) if linha and linha[0] is not None else 0


def aplicar_migracoes(conexao: sqlite3.Connection) -> int:
    """Aplica as migrações pendentes e devolve a versão final.

    Cada script é responsável pela **própria** transação (`BEGIN;` … `COMMIT;`) e
    pelo **próprio** `INSERT INTO schema_versao`. Não é preferência de estilo:
    `Connection.executescript` faz commit do que estiver pendente antes de rodar,
    então envolver a chamada em `with conexao:` daria atomicidade de fachada.

    Nenhuma migração faz `DROP TABLE` (F1-17 §Migrações); se um dia precisar, a
    receita é copiar `chats.sqlite` para `chats.sqlite.bak` antes.
    """
    versao = versao_atual(conexao)
    for numero, arquivo in _migracoes_disponiveis():
        if numero <= versao:
            continue
        sql = arquivo.read_text(encoding="utf-8")
        try:
            conexao.executescript(sql)
        except sqlite3.Error as exc:
            if conexao.in_transaction:
                conexao.execute("ROLLBACK")
            raise ErroNucleo(
                "NU-241",
                f"Falha ao aplicar a migração {arquivo.name}: {exc}",
                {"migracao": arquivo.name},
            ) from exc
        aplicada = versao_atual(conexao)
        if aplicada != numero:
            raise ErroNucleo(
                "NU-241",
                f"A migração {arquivo.name} não gravou schema_versao = {numero}.",
                {"migracao": arquivo.name, "versao_gravada": aplicada},
            )
        versao = numero
    return versao


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    """Abre (criando se preciso) o banco de conversas já migrado.

    WAL é o que permite duas janelas lendo enquanto uma escreve; `busy_timeout`
    é o que faz a segunda escrita esperar em vez de estourar `database is locked`.

    `isolation_level=None` desliga o BEGIN implícito do módulo `sqlite3`: quem abre
    transação é `repositorio._escrita`, com `BEGIN IMMEDIATE`, porque o cálculo do
    `seq` da mensagem precisa do lock de escrita antes de ler o `MAX(seq)`.
    """
    destino = caminho or caminho_banco()
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(destino, timeout=10.0, isolation_level=None)
    except (OSError, sqlite3.Error) as exc:
        raise ErroNucleo(
            "NU-240",
            f"Não foi possível abrir o banco de conversas em {destino}: {exc}",
            {"caminho": str(destino)},
        ) from exc

    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA journal_mode = WAL")
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA busy_timeout = 10000")
    conexao.execute("PRAGMA synchronous = NORMAL")
    aplicar_migracoes(conexao)
    return conexao
