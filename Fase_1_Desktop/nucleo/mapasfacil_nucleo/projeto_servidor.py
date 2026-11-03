"""O projeto do site, como o núcleo o vê (W1-07).

No modo servidor a raiz do workspace é a pasta do projeto e o servidor grava
`.servidor/projeto.json` com o que o usuário já decidiu no site: nome do projeto e folha
(formato + orientação). O núcleo **lê** esse arquivo — nunca o escreve — e usa na memória de
trabalho do agente para não perguntar de novo o que já está decidido.

Fora do modo servidor nada disto existe: `atual()` devolve `None`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import modo_servidor

NOME_ARQUIVO = ".servidor/projeto.json"
CHAVES_VALIDAS: tuple[str, ...] = ("id", "nome", "folha", "dono", "criado_em")

_raiz: Path | None = None


def definir_raiz(raiz: Path | str) -> None:
    """Chamado quando o workspace abre — o servidor não passa a raiz em cada tool."""
    global _raiz
    _raiz = Path(raiz)


def limpar() -> None:
    global _raiz
    _raiz = None


def ler(raiz: Path | str | None = None) -> dict[str, Any] | None:
    """Conteúdo do `projeto.json`, ou `None` se não houver/não estiver em modo servidor."""
    if not modo_servidor():
        return None
    base = Path(raiz) if raiz is not None else _raiz
    if base is None:
        return None
    caminho = base / NOME_ARQUIVO
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(dados, dict):
        return None
    return {chave: dados[chave] for chave in CHAVES_VALIDAS if chave in dados}


def atual() -> dict[str, Any] | None:
    return ler()


def para_memoria() -> dict[str, Any] | None:
    """Recorte que entra na memória de trabalho do agente (nome + folha)."""
    dados = atual()
    if not dados:
        return None
    return {
        "nome": dados.get("nome"),
        "folha": dados.get("folha"),
    }
