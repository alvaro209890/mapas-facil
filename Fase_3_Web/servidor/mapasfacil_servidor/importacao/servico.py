"""Importação de um projeto: copiar, extrair, indexar (W-02 §Indexação e resumo)."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import projetos_repo
from ..erros import ErroServidor
from . import extrair as extrair_mod
from . import upload as upload_mod


@dataclass(frozen=True)
class Raizes:
    projetos: Path
    uploads: Path
    extraido_max_bytes: int


def registrar_importacao(
    con: sqlite3.Connection, *, projeto_id: str, upload_id: str
) -> str:
    importacao_id = uuid.uuid4().hex
    con.execute(
        "INSERT INTO importacoes (id, projeto_id, upload_id, estado, fase, criada_em)"
        " VALUES (?,?,?,?,?,datetime('now'))",
        (importacao_id, projeto_id, upload_id, "na_fila", "verificando"),
    )
    return importacao_id


def marcar_erro(banco: Any, importacao_id: str, *, codigo: str) -> None:
    """Fecha a importação em erro. Usado quando uma exceção inesperada foge do fluxo.

    Sem isto, `TypeError`/`KeyError` deixavam a linha em `rodando` para sempre e o front
    ficava girando (aconteceu no smoke do server em 03/11/2026).
    """
    if banco is None:
        return
    con = banco.conectar()
    try:
        _atualizar(con, importacao_id, estado="erro", erro_codigo=codigo, fim=True)
    finally:
        con.commit()


def _atualizar(
    con: sqlite3.Connection,
    importacao_id: str,
    *,
    estado: str | None = None,
    fase: str | None = None,
    resumo: dict | None = None,
    erro_codigo: str | None = None,
    fim: bool = False,
) -> None:
    campos = []
    valores: list[Any] = []
    if estado is not None:
        campos.append("estado = ?")
        valores.append(estado)
    if fase is not None:
        campos.append("fase = ?")
        valores.append(fase)
    if resumo is not None:
        import json

        campos.append("resumo = ?")
        valores.append(json.dumps(resumo, ensure_ascii=False))
    if erro_codigo is not None:
        campos.append("erro_codigo = ?")
        valores.append(erro_codigo)
    if fim:
        campos.append("fim_em = datetime('now')")
    if not campos:
        return
    valores.append(importacao_id)
    con.execute(f"UPDATE importacoes SET {', '.join(campos)} WHERE id = ?", valores)


def importar(
    *,
    banco,
    raizes: Raizes,
    projeto: projetos_repo.Projeto,
    upload_id: str,
    importacao_id: str,
    pool: Any | None = None,
    chamar=None,
    ao_progresso=None,
) -> dict:
    """Executa a importação de ponta a ponta e devolve o resumo.

    Falha sempre deixa o projeto em `erro` com o código, nunca em estado mentiroso.
    """
    con = banco.conectar()
    try:
        _atualizar(con, importacao_id, estado="rodando", fase="verificando")
        projeto = projetos_repo.transicionar(con, projeto, "importando")

        pasta = raizes.projetos / projeto.id
        pasta.mkdir(parents=True, exist_ok=True)
        up = upload_mod.abrir(raizes.uploads, upload_id)
        destino_zip = pasta / "entrada.zip"
        if not destino_zip.exists():
            origem = raizes.uploads / up.id / "entrada.zip"
            if not origem.is_file():
                raise ErroServidor(
                    "SV-100",
                    "O upload ainda não foi concluído.",
                    status_http=409,
                    o_que_fazer="Termine o envio das partes antes de importar.",
                )
            extrair_mod.copiar_zip(origem, destino_zip)

        pasta_entrada = pasta / "entrada"
        if pasta_entrada.is_dir():
            # Reimportação: guarda a versão anterior em vez de apagar.
            carimbo = str(int(pasta_entrada.stat().st_mtime))
            anterior = pasta / "entrada.anterior" / carimbo
            anterior.parent.mkdir(parents=True, exist_ok=True)
            if not anterior.exists():
                pasta_entrada.rename(anterior)

        _atualizar(con, importacao_id, fase="extraindo")
        resultado = extrair_mod.extrair(
            destino_zip,
            pasta_entrada,
            max_extraido_bytes=raizes.extraido_max_bytes,
            ao_progresso=ao_progresso,
        )
        extrair_mod.marcar_somente_leitura(pasta_entrada)

        _atualizar(con, importacao_id, fase="indexando")
        projeto = projetos_repo.transicionar(con, projeto, "indexando")
        if ao_progresso is not None:
            # A barra da tela troca de "extraindo N de M" para "lendo os shapefiles".
            ao_progresso({"fase": "indexando", "total": resultado.total})

        resumo: dict[str, Any] = {}
        if pool is not None:
            import asyncio

            async def _pedido():
                # Precisa ser corrotina: o app entrega `chamar` como
                # `asyncio.run_coroutine_threadsafe(pedido, laco).result()`, e passar o
                # resultado já aguardado dava `TypeError: A coroutine object is required`
                # (medido no smoke do server em 03/11/2026 — a importação ficava em
                # "rodando" para sempre).
                return await pool.chamar(projeto.id, "workspace.abrir", {"caminho": str(pasta)})

            try:
                # `chamar` existe quando quem chama já está num event loop (o worker do
                # núcleo pertence a esse loop — `asyncio.run` aqui criaria outro e
                # quebraria os pipes). Sem ele, caminho síncrono de teste.
                if chamar is not None:
                    bruto = chamar(_pedido())
                else:
                    bruto = asyncio.run(_pedido())
                resumo = bruto.get("workspace") or {}
                if bruto.get("projeto"):
                    resumo["projeto"] = bruto["projeto"]
            except ErroServidor as exc:
                # Extração boa, indexação falhou: guarda o código e deixa o projeto em erro.
                _atualizar(
                    con,
                    importacao_id,
                    estado="erro",
                    erro_codigo=exc.codigo,
                    fim=True,
                )
                projetos_repo.transicionar(con, projeto, "erro", erro_codigo=exc.codigo)
                raise
        else:
            resumo = {"avisos": [{"codigo": "SV-123", "mensagem": "indexação pendente: worker não configurado"}]}

        if resultado.avisos:
            resumo.setdefault("avisos", [])
            resumo["avisos"] = list(resumo["avisos"]) + resultado.avisos
        resumo["arquivos"] = resultado.total
        resumo["bytes"] = resultado.bytes_extraidos
        resumo["ignorados"] = resultado.ignorados

        projeto = projetos_repo.transicionar(con, projeto, "pronto")
        imovel = (resumo.get("imovel") or {}) if isinstance(resumo, dict) else {}
        if imovel:
            projeto = projetos_repo.atualizar_imovel(con, projeto, imovel)
        _atualizar(con, importacao_id, estado="pronto", fase="pronto", resumo=resumo, fim=True)
        upload_mod.descartar(up)
        return resumo
    except ErroServidor as exc:
        _atualizar(con, importacao_id, estado="erro", erro_codigo=exc.codigo, fim=True)
        atual = projetos_repo.obter(con, projeto.id, usuario_id=projeto.usuario_id, admin=True)
        if atual is not None and atual.estado != "erro":
            try:
                projetos_repo.transicionar(con, atual, "erro", erro_codigo=exc.codigo)
            except ErroServidor:  # pragma: no cover - estado já terminal
                pass
        raise
    finally:
        con.close()


def estado(con: sqlite3.Connection, importacao_id: str) -> dict:
    linha = con.execute(
        "SELECT * FROM importacoes WHERE id = ?", (importacao_id,)
    ).fetchone()
    if linha is None:
        raise ErroServidor("SV-124", "Importação não encontrada.", status_http=404)
    import json

    return {
        "id": linha["id"],
        "projeto_id": linha["projeto_id"],
        "estado": linha["estado"],
        "fase": linha["fase"],
        "resumo": json.loads(linha["resumo"]) if linha["resumo"] else None,
        "erro_codigo": linha["erro_codigo"],
        "criada_em": linha["criada_em"],
        "fim_em": linha["fim_em"],
    }
