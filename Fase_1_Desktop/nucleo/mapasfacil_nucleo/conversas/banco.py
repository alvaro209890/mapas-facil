# Caminho do banco de chats e boot com migrações (F1-17 / D13).

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSAO_ATUAL = 1
_PACOTE = Path(__file__).resolve().parent
_MIGRACOES = _PACOTE / "migracoes"


def diretorio_chats(override: str | Path | None = None) -> Path:
    """Pasta de chats — por usuário sob ``Documentos/database/MapasFacil/<user>/chats``.

    Prioridade:
    1. argumento ``override`` (login ativa a pasta do usuário)
    2. ``MAPASFACIL_CHATS_DIR``
    3. ``MAPASFACIL_DADOS``/chats (legado / boot antes do login)
    4. ``Documentos/database/MapasFacil/_sem_usuario/chats`` (boot frio)
    5. legado APPDATA / XDG
    """
    if override is not None:
        return Path(override).expanduser().resolve()
    env_chats = os.environ.get("MAPASFACIL_CHATS_DIR")
    if env_chats:
        return Path(env_chats).expanduser().resolve()
    env_dados = os.environ.get("MAPASFACIL_DADOS")
    if env_dados:
        return Path(env_dados).expanduser().resolve() / "chats"
    try:
        from mapasfacil_nucleo.dados import raiz_sistema

        return raiz_sistema() / "_sem_usuario" / "chats"
    except Exception:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "MapasFacil" / "chats"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "MapasFacil" / "chats"
    return Path.home() / ".local" / "share" / "MapasFacil" / "chats"


def caminho_banco(diretorio: Path | None = None) -> Path:
    return (diretorio or diretorio_chats()) / "chats.sqlite"


def caminho_anexos(diretorio: Path | None = None) -> Path:
    return (diretorio or diretorio_chats()) / "anexos"


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    """Abre (ou cria) o banco com WAL, foreign_keys e migrações aplicadas."""
    caminho_db = caminho or caminho_banco()
    caminho_db.parent.mkdir(parents=True, exist_ok=True)
    caminho_anexos(caminho_db.parent).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho_db), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    aplicar_migracoes(conn)
    return conn


def versao_atual(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT versao FROM schema_versao LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["versao"]) if row is not None else 0


def aplicar_migracoes(conn: sqlite3.Connection) -> int:
    atual = versao_atual(conn)
    scripts = sorted(_MIGRACOES.glob("*.sql"))
    for script in scripts:
        numero = int(script.name.split("_", 1)[0])
        if numero <= atual:
            continue
        # executescript já comita internamente; não embrulhar em BEGIN/COMMIT
        conn.executescript(script.read_text(encoding="utf-8"))
        atual = numero
    if atual < SCHEMA_VERSAO_ATUAL:
        conn.execute("DELETE FROM schema_versao")
        conn.execute("INSERT INTO schema_versao (versao) VALUES (?)", (SCHEMA_VERSAO_ATUAL,))
        atual = SCHEMA_VERSAO_ATUAL
    return atual
