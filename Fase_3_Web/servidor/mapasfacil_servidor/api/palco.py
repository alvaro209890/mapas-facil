"""Rota do palco (W7-05) — entrega os assets de `Mapas/.preview/<job_id>/`.

O palco da web desenha o que o núcleo produziu, mas **não** pode receber caminho de disco: o
evento traz `Mapas/.preview/<job>/camadas/avn.geojson` e a tela reescreve esse prefixo para cá.
Esta rota tira o prefixo, valida o resto contra uma allowlist de subpastas e devolve o arquivo do
projeto **daquele usuário** — projeto alheio é `404 SV-031` antes de qualquer leitura.

Regras:

* só `camadas/`, `layout/` e `raster/`, um nível, nome de arquivo sem barra;
* extensão da allowlist (`.geojson`, `.png`) — o resto não sai por aqui;
* `Cache-Control: private, max-age=3600`: é dado do cliente, CDN nenhuma guarda;
* arquivo ausente é `SV-402`/404 — para o palco não interessa se o job existe ou não.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from .. import projetos_repo
from ..auth import contas
from ..erros import ErroServidor
from . import deps

router = APIRouter(prefix="/projetos", tags=["palco"])

SUBPASTAS = frozenset({"camadas", "layout", "raster"})
TIPOS = {".geojson": "application/geo+json", ".png": "image/png"}
CACHE = "private, max-age=3600"


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


def _ausente(detalhes: dict) -> ErroServidor:
    return ErroServidor(
        "SV-402",
        "Arquivo de palco não encontrado.",
        status_http=404,
        porque="O arquivo pedido não existe para este job ou não é um asset de palco.",
        o_que_fazer="Recarregue a página: o palco se reconstrói pelo replay dos eventos.",
        detalhes=detalhes,
    )


def _resolver(raiz: Path, job_id: str, resto: str) -> Path:
    bruto = (resto or "").replace("\\", "/").strip()
    partes = [p for p in bruto.split("/") if p not in ("", ".")]
    if "\x00" in bruto or ".." in partes or len(partes) != 2:
        raise _ausente({"resto": bruto[:120]})
    sub, arquivo = partes
    if sub not in SUBPASTAS:
        raise _ausente({"resto": bruto[:120], "permitidos": sorted(SUBPASTAS)})
    base = (raiz / "Mapas" / ".preview").resolve()
    alvo = (base / job_id / sub / arquivo).resolve()
    if not str(alvo).startswith(str(base)) or alvo.suffix.lower() not in TIPOS:
        raise _ausente({"resto": bruto[:120]})
    if not alvo.is_file():
        raise _ausente({"job_id": job_id, "resto": bruto[:120]})
    return alvo


@router.get("/{projeto_id}/palco/{job_id}/{resto:path}")
def ler_palco(
    projeto_id: str,
    job_id: str,
    resto: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> FileResponse:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    raiz = (_pasta_projetos(estado) / projeto.id).resolve()
    alvo = _resolver(raiz, job_id, resto)
    return FileResponse(
        alvo,
        media_type=TIPOS[alvo.suffix.lower()],
        headers={
            "Cache-Control": CACHE,
            "X-Content-Type-Options": "nosniff",
        },
    )
