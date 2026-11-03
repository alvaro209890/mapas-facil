"""Serviço da SPA (W6-10).

O FastAPI entrega o build do Vite (`web/dist`) do mesmo host, com três regras:

1. **Assets com hash** (`/assets/index-7f3a.js`) levam `Cache-Control: immutable` por um ano —
   o nome muda quando o conteúdo muda, então cache eterno é seguro;
2. **`index.html` é `no-cache`** — senão o navegador fica preso no build antigo e o usuário
   jura que "nada mudou";
3. **Rota do SPA**: qualquer caminho que não seja `/api/...` e não exista como arquivo devolve
   `index.html` (recarregar `/projetos/p1` no meio do trabalho não pode dar 404 — critério de
   sucesso do W-00).

Sem `dist` (ambiente de desenvolvimento), nada é montado: a API responde e o `pnpm dev` cuida
do front. Ausência de build não pode virar 500.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

CACHE_ASSET = "public, max-age=31536000, immutable"
CACHE_HTML = "no-cache, must-revalidate"

_TIPOS = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ico": "image/x-icon",
    ".map": "application/json",
    ".txt": "text/plain; charset=utf-8",
}


def pasta_dist(raiz: Path) -> Path:
    """Onde está o build. `MF_WEB_DIST` manda quando o deploy separa os diretórios."""
    do_ambiente = os.environ.get("MF_WEB_DIST", "").strip()
    if do_ambiente:
        return Path(do_ambiente)
    return Path(raiz) / "web" / "dist"


def _tipo(caminho: Path) -> str:
    return _TIPOS.get(caminho.suffix.lower(), "application/octet-stream")


def montar_estaticos(app: FastAPI, dist: Path) -> bool:
    """Monta a SPA. Devolve `False` quando não há build para servir."""
    dist = Path(dist)
    indice = dist / "index.html"
    if not indice.is_file():
        return False

    assets = dist / "assets"

    @app.get("/assets/{caminho:path}", include_in_schema=False)
    def asset(caminho: str) -> FileResponse:
        alvo = (assets / caminho).resolve()
        if not str(alvo).startswith(str(assets.resolve())) or not alvo.is_file():
            return JSONResponse({"erro": {"codigo": "SV-401", "mensagem": "Arquivo não encontrado."}},
                                status_code=404)
        return FileResponse(alvo, media_type=_tipo(alvo), headers={"Cache-Control": CACHE_ASSET})

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):  # type: ignore[no-untyped-def]
        # A API tem precedência: um `/api/...` desconhecido é 404 de API, nunca o index.html.
        if caminho.startswith("api/"):
            return JSONResponse(
                {"erro": {"codigo": "SV-404", "mensagem": "Rota de API não encontrada."}},
                status_code=404,
            )
        if caminho:
            candidato = (dist / caminho).resolve()
            if str(candidato).startswith(str(dist.resolve())) and candidato.is_file():
                cache = CACHE_ASSET if caminho.startswith("assets/") else CACHE_HTML
                return FileResponse(candidato, media_type=_tipo(candidato), headers={"Cache-Control": cache})
        return FileResponse(indice, media_type=_TIPOS[".html"], headers={"Cache-Control": CACHE_HTML})

    return True
