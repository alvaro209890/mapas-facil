"""Entrega de arquivos do projeto (W-03 §Versões e arquivos).

A allowlist é **fechada**: só `Mapas/` e `MXD/` saem por aqui. `SHP/` e o resto vão dentro
do `.zip` do pacote — assim um caminho novo no projeto não vira download acidental.

Códigos:

- ``SV-401`` (404) — caminho fora da allowlist, ou arquivo que não existe;
- ``SV-402`` (400) — caminho com `..`, absoluto ou com NUL.

`Range` é suportado pelo `FileResponse` do Starlette, o que permite ao navegador retomar um
PDF grande em vez de baixar de novo.
"""

from __future__ import annotations

import datetime as _dt
import mimetypes
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from .. import projetos_repo
from ..auth import contas
from ..erros import ErroServidor
from . import deps

router = APIRouter(prefix="/projetos", tags=["arquivos"])

PREFIXOS_PERMITIDOS = ("Mapas/", "MXD/")

_TIPOS = {
    ".mxd": "application/octet-stream",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".geojson": "application/geo+json",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
}


def _admin(usuario: contas.Usuario) -> bool:
    return getattr(usuario, "papel", "usuario") == "admin"


def _pasta_projetos(estado: deps.AppState) -> Path:
    cfg = estado.config
    pasta = getattr(cfg, "projetos", None)
    if pasta is None:
        raise ErroServidor(
            "SV-000",
            "Servidor sem configuração de pastas.",
            status_http=500,
            o_que_fazer="Confira MF_RAIZ/MF_SEGREDOS no ambiente do serviço.",
        )
    return Path(pasta)


def _validar_caminho(caminho: str) -> str:
    bruto = (caminho or "").replace("\\", "/").strip()
    if not bruto:
        raise ErroServidor("SV-401", "Arquivo não informado.", status_http=404)
    if "\x00" in bruto or bruto.startswith("/") or ".." in bruto.split("/"):
        raise ErroServidor(
            "SV-402",
            "Caminho de arquivo inválido.",
            status_http=400,
            porque="O caminho pedido sai da pasta do projeto.",
            o_que_fazer="Peça o arquivo pelo nome que aparece na lista de versões.",
        )
    if not bruto.startswith(PREFIXOS_PERMITIDOS):
        raise ErroServidor(
            "SV-401",
            "Este arquivo não é servido por download.",
            status_http=404,
            porque="Só `Mapas/` e `MXD/` são entregues avulsos; o resto vai no pacote `.zip`.",
            detalhes={"permitidos": list(PREFIXOS_PERMITIDOS)},
        )
    return bruto


def _nome_amigavel(caminho: str, projeto_nome: str) -> str:
    """`Mapas/v003/mapa.pdf` do projeto "Boa Vista" vira `Boa Vista v003 mapa.pdf`."""
    partes = caminho.split("/")
    arquivo = partes[-1]
    versao = next((p for p in reversed(partes) if p.startswith("v") and p[1:].isdigit()), "")
    base = f"{projeto_nome} {versao} {arquivo}".strip()
    return "_".join(base.split()).replace("/", "-")


@router.get("/{projeto_id}/arquivos/{caminho:path}")
def baixar(
    projeto_id: str,
    caminho: str,
    anexo: bool = Query(default=False, description="true = força download (Content-Disposition: attachment)"),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> FileResponse:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    relativo = _validar_caminho(caminho)
    raiz = (_pasta_projetos(estado) / projeto.id).resolve()
    alvo = (raiz / relativo).resolve()
    # Segunda barreira: mesmo com a allowlist, o alvo tem de estar dentro do projeto
    # (symlink para fora não passa).
    if not str(alvo).startswith(str(raiz)) or not alvo.is_file():
        raise ErroServidor(
            "SV-401",
            "Arquivo não encontrado neste projeto.",
            status_http=404,
            o_que_fazer="Abra a lista de versões e baixe o artefato por ela.",
            detalhes={"caminho": relativo},
        )

    tipo = _TIPOS.get(alvo.suffix.lower()) or mimetypes.guess_type(alvo.name)[0]
    nome = _nome_amigavel(relativo, projeto.nome)
    disposicao = "attachment" if anexo else "inline"
    return FileResponse(
        alvo,
        media_type=tipo or "application/octet-stream",
        filename=nome,
        content_disposition_type=disposicao,
        headers={
            "Cache-Control": "private, max-age=60",
            "X-Content-Type-Options": "nosniff",
            "Last-Modified": _dt.datetime.fromtimestamp(
                alvo.stat().st_mtime, tz=_dt.timezone.utc
            ).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        },
    )
