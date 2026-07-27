# Leitura da chave DeepSeek — nunca loga o valor.
#
# Produto (piloto Acer): após login a chave do projeto é sincronizada no cofre
# (`agente.provisao`). Leitura: override → env → cofre → provisão/secrets.

from __future__ import annotations

from pathlib import Path

from mapasfacil_nucleo.config import raiz_repositorio


def ler_chave_deepseek(*, override: str | None = None) -> str | None:
    """Ordem: argumento → ``DEEPSEEK_API_KEY`` → cofre → provisão do projeto.

    A provisão cobre ``provisao.local.json`` e ``secrets.local.json`` (dev).
    """
    if override is not None:
        chave = override.strip()
        return chave or None

    import os

    env = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env:
        return env

    try:
        from mapasfacil_nucleo import cofre

        do_cofre = cofre.usar("deepseek_api_key")
        if do_cofre:
            return do_cofre
    except Exception:
        # Cofre indisponível (sem keyring) — cai na provisão.
        pass

    from mapasfacil_nucleo.agente.provisao import ler_chave_projeto

    return ler_chave_projeto()


def caminho_secrets() -> Path:
    return raiz_repositorio() / "secrets.local.json"
