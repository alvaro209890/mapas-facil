"""Provisão da chave DeepSeek do projeto (desbloqueio automático no login).

A chave **nunca** é commitada. Ordem de leitura:
1. ``DEEPSEEK_API_KEY`` (env)
2. ``MAPASFACIL_PROVISAO_PATH`` (JSON com deepseek_api_key)
3. ``Documentos/database/MapasFacil/provisao.local.json``
4. ``secrets.local.json`` / ``secrets.json`` na raiz do monorepo (dev neste PC)

No login, ``sincronizar_chave_projeto_no_cofre()`` grava no cofre do SO para o
resto do app (doctor, chat, Preferências) ver a chave como ativa.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.dados import (
    caminho_provisao,
    gravar_provisao_arquivo,
    ler_provisao_arquivo,
)


def _ler_secrets_repo() -> str | None:
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


def ler_chave_projeto() -> str | None:
    """Chave do projeto (teste/piloto). Nunca logar o retorno."""
    env = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env:
        return env

    path_env = (os.environ.get("MAPASFACIL_PROVISAO_PATH") or "").strip()
    if path_env:
        dados = ler_provisao_arquivo(Path(path_env))
        if dados.get("deepseek_api_key"):
            return dados["deepseek_api_key"]

    dados_local = ler_provisao_arquivo()
    if dados_local.get("deepseek_api_key"):
        return dados_local["deepseek_api_key"]

    return _ler_secrets_repo()


def espelhar_secrets_para_provisao(destino: Path | None = None) -> bool:
    """Se há secrets.local.json, espelha para provisao.local.json.

    Assim o instalador/Electron neste PC e sessões futuras leem a mesma chave
    sem depender do monorepo.
    """
    chave = _ler_secrets_repo()
    if not chave:
        return False
    alvo = destino or caminho_provisao()
    if alvo.is_file():
        atual = ler_provisao_arquivo(alvo)
        if atual.get("deepseek_api_key") == chave:
            return True
    alvo.parent.mkdir(parents=True, exist_ok=True)
    # Preserva outras chaves já provisionadas.
    base = ler_provisao_arquivo(alvo) if alvo.is_file() else {}
    base["deepseek_api_key"] = chave
    # SEMA/Planet do secrets, se existirem
    for nome in ("secrets.local.json", "secrets.json"):
        caminho = raiz_repositorio() / nome
        if not caminho.is_file():
            continue
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for k in ("sema_authkey", "planet_api_key"):
            v = (dados.get(k) or "").strip()
            if v:
                base[k] = v
        break
    gravar_provisao_arquivo(base, alvo)
    return True


def sincronizar_chave_projeto_no_cofre() -> dict[str, bool | str]:
    """Garante DeepSeek no cofre a partir da chave do projeto.

    Retorno só com booleans/status — nunca o segredo.
    """
    from mapasfacil_nucleo import cofre

    chave = ler_chave_projeto()
    if not chave:
        return {"ok": False, "motivo": "provisao_ausente"}
    try:
        cofre.definir("deepseek_api_key", chave)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "motivo": exc.__class__.__name__}
    return {"ok": True, "motivo": "cofre"}
