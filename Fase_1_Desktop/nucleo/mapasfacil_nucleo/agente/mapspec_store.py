# Persistência do MapSpec vivo por conversa (M7) — sobrevive ao reinício do sidecar.
#
# Arquivo: `{MAPASFACIL_DADOS}/chats/mapspecs/<conversation_id>.json`
# O banco só guarda id/versão nas mensagens; o JSON completo fica aqui.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.conversas.banco import diretorio_chats


def pasta_mapspecs(diretorio_chats_override: Path | None = None) -> Path:
    return (diretorio_chats_override or diretorio_chats()) / "mapspecs"


def caminho_mapspec(conversation_id: str, diretorio_chats_override: Path | None = None) -> Path:
    return pasta_mapspecs(diretorio_chats_override) / f"{conversation_id}.json"


def carregar_mapspec(
    conversation_id: str,
    *,
    diretorio_chats_override: Path | None = None,
) -> dict[str, Any] | None:
    caminho = caminho_mapspec(conversation_id, diretorio_chats_override)
    if not caminho.is_file():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


def gravar_mapspec(
    conversation_id: str,
    mapspec: dict[str, Any],
    *,
    diretorio_chats_override: Path | None = None,
) -> Path:
    pasta = pasta_mapspecs(diretorio_chats_override)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = caminho_mapspec(conversation_id, diretorio_chats_override)
    caminho.write_text(
        json.dumps(mapspec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return caminho


def apagar_mapspec(
    conversation_id: str,
    *,
    diretorio_chats_override: Path | None = None,
) -> None:
    caminho = caminho_mapspec(conversation_id, diretorio_chats_override)
    if caminho.is_file():
        caminho.unlink()
