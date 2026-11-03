"""App FastAPI — `/api/v1` (W-03).

Montagem explícita: o estado (banco, limitador, config, pool) chega por
`create_app`, então os testes sobem o app com banco em `tmp_path` sem tocar em
ambiente nenhum.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .api import admin, auth, deps, importacao, projetos
from .db import Banco
from .erros import ErroServidor

API = "/api/v1"


def _corpo_erro(exc: ErroServidor) -> dict:
    return exc.para_dict()


def create_app(
    *,
    banco: Banco,
    admin_email: str | None = None,
    origem: str | None = None,
    config: object | None = None,
) -> FastAPI:
    app = FastAPI(title="Mapas Fácil", version=__version__, docs_url=None, redoc_url=None)
    app.state.mf = deps.AppState(banco=banco, admin_email=admin_email, config=config)
    app.state.mf_origem = origem

    @app.exception_handler(ErroServidor)
    async def _erro_servidor(_request: Request, exc: ErroServidor) -> JSONResponse:
        return JSONResponse(status_code=exc.status_http, content=_corpo_erro(exc))

    @app.exception_handler(Exception)
    async def _erro_generico(_request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        return JSONResponse(
            status_code=500,
            content={
                "erro": {
                    "codigo": "SV-099",
                    "mensagem": "Falha interna do servidor.",
                    "detalhes": {"tipo": type(exc).__name__},
                }
            },
        )

    app.include_router(auth.router, prefix=API)
    app.include_router(projetos.router, prefix=API)
    app.include_router(importacao.router, prefix=API)
    app.include_router(admin.router, prefix=API)

    @app.get(f"{API}/saude")
    def saude() -> dict:
        """Público: só o suficiente para saber que o servidor está de pé."""
        return {
            "ok": True,
            "versao": __version__,
            "schema": banco.versao(),
            "espaco_disco_gb": _disco_gb(config),
        }

    return app


def _disco_gb(config: object | None) -> float | None:
    import shutil

    raiz = Path(str(getattr(config, "raiz", ".") or "."))
    try:
        return round(shutil.disk_usage(raiz).free / (1024**3), 1)
    except OSError:
        return None


def app_do_ambiente() -> FastAPI:
    """App de produção: lê a config do ambiente e migra o banco."""
    from . import config as config_mod

    cfg = config_mod.carregar()
    banco = Banco(cfg.banco)
    banco.migrar()
    return create_app(
        banco=banco,
        admin_email=cfg.admin_email,
        origem=cfg.url_publica,
        config=cfg,
    )


__all__ = ["create_app", "app_do_ambiente", "json"]
