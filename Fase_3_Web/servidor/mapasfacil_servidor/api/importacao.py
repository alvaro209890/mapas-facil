"""Rotas de upload por partes e de importação (W-02/W-03)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response

from .. import projetos_repo
from ..auth import contas, sessoes
from ..erros import ErroServidor
from ..importacao import servico as importacao_servico
from ..importacao import upload as upload_mod
from . import deps, modelos

router = APIRouter(tags=["importacao"])


def _raizes(estado: deps.AppState) -> importacao_servico.Raizes:
    from ..config import Config

    cfg = estado.config
    if not isinstance(cfg, Config):
        raise ErroServidor(
            "SV-000",
            "Servidor sem configuração de pastas.",
            status_http=500,
        )
    return importacao_servico.Raizes(
        projetos=cfg.projetos,
        uploads=cfg.uploads,
        extraido_max_bytes=cfg.extraido_max_mb * 1024 * 1024,
    )


def _limite_upload(estado: deps.AppState) -> int:
    from ..config import Config

    cfg = estado.config
    if isinstance(cfg, Config):
        return cfg.upload_max_mb * 1024 * 1024
    return 2 * 1024 * 1024 * 1024


@router.post("/uploads", status_code=201)
def criar_upload(
    corpo: dict,
    estado: deps.AppState = Depends(deps.pegar_estado),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    nome = str(corpo.get("nome") or "entrada.zip")
    try:
        tamanho = int(corpo.get("tamanho") or 0)
    except (TypeError, ValueError):
        raise ErroServidor("SV-100", "Tamanho inválido.", status_http=400)
    raizes = _raizes(estado)
    parte_mb = int(getattr(estado.config, "upload_parte_mb", upload_mod.PARTE_PADRAO_MB))
    upload = upload_mod.criar(
        raizes.uploads,
        nome=nome,
        tamanho=tamanho,
        parte_mb=parte_mb,
        tamanho_max_bytes=_limite_upload(estado),
    )
    return upload.para_json()


@router.put("/uploads/{upload_id}/partes/{numero}", status_code=204)
async def enviar_parte(
    upload_id: str,
    numero: int,
    request: Request,
    estado: deps.AppState = Depends(deps.pegar_estado),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    x_parte_sha256: str | None = Header(default=None, alias="X-Parte-SHA256"),
) -> Response:
    dados = await request.body()
    raizes = _raizes(estado)
    upload = upload_mod.abrir(raizes.uploads, upload_id)
    upload_mod.gravar_parte(
        upload, numero, dados, sha256_declarado=x_parte_sha256
    )
    return Response(status_code=204)


@router.get("/uploads/{upload_id}")
def estado_upload(
    upload_id: str,
    estado: deps.AppState = Depends(deps.pegar_estado),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    raizes = _raizes(estado)
    return upload_mod.abrir(raizes.uploads, upload_id).para_json()


@router.post("/uploads/{upload_id}/concluir")
def concluir_upload(
    upload_id: str,
    corpo: dict,
    estado: deps.AppState = Depends(deps.pegar_estado),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    raizes = _raizes(estado)
    upload = upload_mod.abrir(raizes.uploads, upload_id)
    destino = raizes.uploads / upload.id / "entrada.zip"
    info = upload_mod.concluir(
        upload,
        hash_partes_declarado=str(corpo.get("hash_partes") or ""),
        destino=destino,
    )
    return {"sha256": info["sha256"], "tamanho": info["tamanho"], "upload_id": upload.id}


@router.post("/projetos/{projeto_id}/importacao", status_code=202)
def criar_importacao(
    projeto_id: str,
    corpo: modelos.ImportacaoNova,
    tarefas: BackgroundTasks,
    estado: deps.AppState = Depends(deps.pegar_estado),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado not in {"aguardando_zip", "erro", "pronto"}:
        raise ErroServidor(
            "SV-090",
            f"Não dá para importar com o projeto em {projeto.estado!r}.",
            status_http=409,
        )
    raizes = _raizes(estado)
    upload = upload_mod.abrir(raizes.uploads, corpo.upload_id)
    if not (raizes.uploads / upload.id / "entrada.zip").is_file():
        raise ErroServidor(
            "SV-100",
            "O upload ainda não foi concluído.",
            status_http=409,
            o_que_fazer="Envie todas as partes e chame /concluir antes de importar.",
        )
    importacao_id = importacao_servico.registrar_importacao(
        con, projeto_id=projeto.id, upload_id=upload.id
    )

    banco = estado.banco
    pool = getattr(estado, "pool", None)
    raiz_projeto = raizes.projetos / projeto.id
    hub = estado.hub

    def _emitir(evento: str, dados: dict, *, job_id: str | None = None) -> None:
        from ..eventos.log import LogEventos

        envelope = LogEventos(raiz_projeto).registrar(
            origem="servidor", evento=evento, dados=dados, job_id=job_id
        )
        hub.publicar(projeto.id, envelope)

    def _rodar() -> None:
        # Roda **depois** da resposta: erro aqui já está registrado em
        # `importacoes.erro_codigo` e no estado do projeto — não pode subir como
        # exceção não tratada (o Starlette estouraria "response already started").
        from ..erros import ErroServidor

        _emitir("projeto.estado", {"estado": "importando"})
        try:
            resumo = importacao_servico.importar(
                banco=banco,
                raizes=raizes,
                projeto=projeto,
                upload_id=upload.id,
                importacao_id=importacao_id,
                pool=pool,
                ao_progresso=lambda dados: _emitir("importacao.progresso", dados),
            )
        except ErroServidor as exc:
            _emitir("projeto.estado", {"estado": "erro", "erro_codigo": exc.codigo})
            return
        _emitir(
            "projeto.estado",
            {"estado": "pronto", "resumo": resumo if isinstance(resumo, dict) else None},
        )

    tarefas.add_task(_rodar)
    return {"importacao_id": importacao_id}


@router.get("/importacoes/{importacao_id}")
def ver_importacao(
    importacao_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    dados = importacao_servico.estado(con, importacao_id)
    projetos_repo.exigir(
        con,
        dados["projeto_id"],
        usuario_id=usuario.id,
        admin=usuario.papel == "admin",
    )
    return dados


@router.get("/projetos/{projeto_id}/resumo")
def resumo(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=usuario.papel == "admin"
    )
    linha = con.execute(
        "SELECT resumo FROM importacoes WHERE projeto_id = ? AND estado = 'pronto'"
        " ORDER BY criada_em DESC LIMIT 1",
        (projeto.id,),
    ).fetchone()
    import json

    return {
        "projeto_id": projeto.id,
        "estado": projeto.estado,
        "resumo": json.loads(linha["resumo"]) if linha and linha["resumo"] else None,
    }
