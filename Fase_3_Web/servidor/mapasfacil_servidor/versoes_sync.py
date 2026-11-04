"""Versões que o núcleo gerou → banco do servidor e evento `versao.criada` (W-04 §Registro).

O núcleo escreve `Mapas/vNNN/` quando o agente chama `gerar_mapa`; o servidor é quem lista e
entrega essas versões para a web. Sem este passo, o chat dizia "o mapa está pronto" e a tela
continuava em "sem versões", sem botão de baixar.

`sincronizar` é idempotente e barato: registra só a pasta que o banco ainda não conhece e
reconfere a mais recente (o PDF sai antes da planilha). Por isso pode ser chamado no fim de
um turno, logo depois de `gerar_mapa` e também ao abrir o projeto (que cura projetos antigos).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Callable

from . import projetos_repo
from .ponte import versao as versao_mod

_LOG = logging.getLogger("mapasfacil.versoes")


def raiz_do_projeto(estado: Any, projeto_id: str) -> Path:
    """Pasta do projeto no disco (mesma regra de `api/mensagens._raiz`)."""
    pasta = getattr(getattr(estado, "config", None), "projetos", None)
    if pasta is not None:
        return Path(pasta) / projeto_id
    return Path(str(estado.banco.caminho)).parent / "projetos" / projeto_id


def _numeros_em_disco(raiz: Path) -> list[int]:
    pasta = raiz / "Mapas"
    if not pasta.is_dir():
        return []
    numeros = []
    for filho in pasta.iterdir():
        nome = filho.name
        if filho.is_dir() and nome.startswith("v") and nome[1:].isdigit():
            numeros.append(int(nome[1:]))
    return sorted(numeros)


def sincronizar(con: sqlite3.Connection, projeto_id: str, raiz: Path) -> list[dict[str, Any]]:
    """Registra as versões novas (ou que mudaram) e devolve-as no formato de `versoes()`."""
    numeros = _numeros_em_disco(raiz)
    if not numeros:
        return []
    conhecidas = {
        int(linha["numero"]): json.loads(linha["artefatos"] or "{}")
        for linha in con.execute(
            "SELECT numero, artefatos FROM versoes WHERE projeto_id = ?", (projeto_id,)
        )
    }
    projeto = projetos_repo.obter(con, projeto_id, usuario_id="", admin=True)
    if projeto is None:
        return []
    mais_recente = numeros[-1]
    mudaram: list[int] = []
    for numero in numeros:
        if numero in conhecidas and numero != mais_recente:
            continue
        registro = versao_mod.montar(raiz, numero)
        if "pdf" not in registro.artefatos:
            continue  # geração ainda escrevendo, ou falhou antes do PDF
        if versao_mod.gerar_miniatura(raiz, numero):
            registro = versao_mod.montar(raiz, numero)
        if conhecidas.get(numero) == registro.artefatos:
            continue
        projetos_repo.registrar_versao(
            con,
            projeto,
            numero=registro.numero,
            pasta=registro.pasta,
            conforme=registro.conforme,
            miniatura=registro.miniatura,
            artefatos=registro.artefatos,
            validacao=registro.validacao,
        )
        mudaram.append(numero)
    if not mudaram:
        return []
    # `registrar_versao` aponta `versao_atual` para a última gravada; garante a maior.
    con.execute(
        "UPDATE projetos SET versao_atual = ? WHERE id = ? AND versao_atual < ?",
        (mais_recente, projeto_id, mais_recente),
    )
    todas = {v["numero"]: v for v in projetos_repo.versoes(con, projeto_id)}
    return [todas[n] for n in mudaram if n in todas]


def sincronizar_seguro(con: sqlite3.Connection, projeto_id: str, raiz: Path) -> list[dict[str, Any]]:
    """`sincronizar` que nunca derruba a rota que o chamou (HD lento, PNG corrompido…)."""
    try:
        return sincronizar(con, projeto_id, raiz)
    except Exception as exc:  # noqa: BLE001 — listar o projeto vale mais que o registro
        _LOG.warning("falha ao sincronizar versões de %s: %s", projeto_id, exc)
        return []


async def publicar_novas(
    *,
    banco: Any,
    projeto_id: str,
    raiz: Path,
    emitir: Callable[[str, dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    """Sincroniza fora do loop (o HD é lento) e emite `versao.criada` para cada versão nova."""

    def _rodar() -> list[dict[str, Any]]:
        con = banco.conectar()
        try:
            return sincronizar_seguro(con, projeto_id, raiz)
        finally:
            con.close()

    novas = await asyncio.to_thread(_rodar)
    for nova in novas:
        emitir("versao.criada", {"projeto_id": projeto_id, "versao": nova})
    return novas
