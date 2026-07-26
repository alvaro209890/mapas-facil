# Caminho do banco de contas locais e boot com migrações (F1-14 / M5).

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSAO_ATUAL = 1
_PACOTE = Path(__file__).resolve().parent
_MIGRACOES = _PACOTE / "migracoes"


def diretorio_contas(override: str | Path | None = None) -> Path:
    """Pasta `%APPDATA%/MapasFacil/contas` (ou XDG / env em Linux/dev).

    Prioridade:
    1. argumento ``override``
    2. ``MAPASFACIL_CONTAS_DIR``
    3. ``MAPASFACIL_DADOS``/contas
    4. ``%APPDATA%/MapasFacil/contas`` ou ``$XDG_DATA_HOME/MapasFacil/contas``
    """
    if override is not None:
        return Path(override).expanduser().resolve()
    env_contas = os.environ.get("MAPASFACIL_CONTAS_DIR")
    if env_contas:
        return Path(env_contas).expanduser().resolve()
    env_dados = os.environ.get("MAPASFACIL_DADOS")
    if env_dados:
        return Path(env_dados).expanduser().resolve() / "contas"
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "MapasFacil" / "contas"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "MapasFacil" / "contas"
    return Path.home() / ".local" / "share" / "MapasFacil" / "contas"


def caminho_banco(diretorio: Path | None = None) -> Path:
    return (diretorio or diretorio_contas()) / "contas.sqlite"


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    caminho_db = caminho or caminho_banco()
    caminho_db.parent.mkdir(parents=True, exist_ok=True)
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
        conn.executescript(script.read_text(encoding="utf-8"))
        atual = numero
    if atual < SCHEMA_VERSAO_ATUAL:
        conn.execute("DELETE FROM schema_versao")
        conn.execute("INSERT INTO schema_versao (versao) VALUES (?)", (SCHEMA_VERSAO_ATUAL,))
        atual = SCHEMA_VERSAO_ATUAL
    return atual
