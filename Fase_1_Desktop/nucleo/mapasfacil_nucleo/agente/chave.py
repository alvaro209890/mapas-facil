# Leitura da chave DeepSeek (BYOK) — nunca loga o valor.

from __future__ import annotations

import json
import os
from pathlib import Path

from mapasfacil_nucleo.config import raiz_repositorio


def ler_chave_deepseek(*, override: str | None = None) -> str | None:
    """Ordem: argumento → ``DEEPSEEK_API_KEY`` → cofre (A11) → ``secrets.local.json``.

    Em produção a chave vive no cofre do SO. Em dev, ``secrets.local.json``
    (gitignored) continua válido.
    """
    if override is not None:
        chave = override.strip()
        return chave or None
    env = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env:
        return env

    try:
        from mapasfacil_nucleo import cofre

        do_cofre = cofre.usar("deepseek_api_key")
        if do_cofre:
            return do_cofre
    except Exception:
        # Cofre indisponível (sem keyring) — cai no arquivo local.
        pass

    for nome in ("secrets.local.json", "secrets.json"):
        caminho = raiz_repositorio() / nome
        if not caminho.is_file():
            continue
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        chave = (dados.get("deepseek_api_key") or "").strip()
        if chave:
            return chave
    return None


def caminho_secrets() -> Path:
    return raiz_repositorio() / "secrets.local.json"
