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


# Chaves que o app provisiona sozinho no login. SEMA e Planet destravam as
# camadas do catálogo (30 das 41 exigem `sema_authkey`) — sem elas o usuário
# final bateria em `NU-102` pedindo configuração manual.
CHAVES_PROVISIONADAS: tuple[str, ...] = (
    "deepseek_api_key",
    "sema_authkey",
    "planet_api_key",
)

# Env var por chave — mantém `DEEPSEEK_API_KEY`, que já era contrato.
_ENV_POR_CHAVE: dict[str, str] = {
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "sema_authkey": "MAPASFACIL_SEMA_AUTHKEY",
    "planet_api_key": "MAPASFACIL_PLANET_API_KEY",
}


def _ler_secrets_repo(chave: str = "deepseek_api_key") -> str | None:
    for nome in ("secrets.local.json", "secrets.json"):
        caminho = raiz_repositorio() / nome
        if not caminho.is_file():
            continue
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        valor = (dados.get(chave) or "").strip()
        if valor:
            return valor
    return None


def ler_chave_provisionada(chave: str) -> str | None:
    """Valor de uma chave do projeto. Nunca logar o retorno."""
    env_nome = _ENV_POR_CHAVE.get(chave)
    if env_nome:
        env = (os.environ.get(env_nome) or "").strip()
        if env:
            return env

    path_env = (os.environ.get("MAPASFACIL_PROVISAO_PATH") or "").strip()
    if path_env:
        dados = ler_provisao_arquivo(Path(path_env))
        if dados.get(chave):
            return dados[chave]

    dados_local = ler_provisao_arquivo()
    if dados_local.get(chave):
        return dados_local[chave]

    return _ler_secrets_repo(chave)


def ler_chave_projeto() -> str | None:
    """Chave DeepSeek do projeto (teste/piloto). Nunca logar o retorno."""
    return ler_chave_provisionada("deepseek_api_key")


def espelhar_secrets_para_provisao(destino: Path | None = None) -> bool:
    """Se há secrets.local.json, espelha para provisao.local.json.

    Assim o instalador/Electron neste PC e sessões futuras leem a mesma chave
    sem depender do monorepo.
    """
    do_secrets = {
        chave: valor
        for chave in CHAVES_PROVISIONADAS
        if (valor := _ler_secrets_repo(chave))
    }
    if not do_secrets:
        return False
    alvo = destino or caminho_provisao()
    base = ler_provisao_arquivo(alvo) if alvo.is_file() else {}
    if all(base.get(chave) == valor for chave, valor in do_secrets.items()):
        return True
    alvo.parent.mkdir(parents=True, exist_ok=True)
    base.update(do_secrets)  # preserva chaves já provisionadas
    gravar_provisao_arquivo(base, alvo)
    return True


def sincronizar_chave_projeto_no_cofre() -> dict[str, bool | str]:
    """Grava no cofre as chaves do projeto (DeepSeek, SEMA, Planet).

    SEMA/Planet são o que destrava as camadas do catálogo sem o usuário
    configurar nada. Retorno só com booleans/status — nunca o segredo.
    """
    from mapasfacil_nucleo import cofre

    sincronizadas: list[str] = []
    for chave in CHAVES_PROVISIONADAS:
        valor = ler_chave_provisionada(chave)
        if not valor:
            continue
        try:
            cofre.definir(chave, valor)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "motivo": exc.__class__.__name__}
        sincronizadas.append(chave)

    if not sincronizadas:
        return {"ok": False, "motivo": "provisao_ausente"}
    return {"ok": True, "motivo": "cofre", "chaves": ",".join(sincronizadas)}
