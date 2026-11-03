"""App FastAPI — `/api/v1` (W-03).

Montagem explícita: o estado (banco, limitador, config, pool) chega por
`create_app`, então os testes sobem o app com banco em `tmp_path` sem tocar em
ambiente nenhum.
"""

from __future__ import annotations

import contextlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .api import admin, arquivos, auth, deps, eventos, importacao, mensagens, projetos, sugestoes
from .db import Banco
from .erros import ErroServidor
from .estaticos import montar_estaticos, pasta_dist

API = "/api/v1"


def _corpo_erro(exc: ErroServidor) -> dict:
    return exc.para_dict()


def create_app(
    *,
    banco: Banco,
    admin_email: str | None = None,
    origem: str | None = None,
    config: object | None = None,
    pool: object | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        yield
        # Desligamento: nenhum worker fica órfão segurando subprocesso.
        if pool is not None:
            with contextlib.suppress(Exception):
                await pool.encerrar_todos(motivo="desligando")

    app = FastAPI(
        title="Mapas Fácil",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=ciclo,
    )
    app.state.mf = deps.AppState(
        banco=banco, admin_email=admin_email, config=config, pool=pool
    )
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
    app.include_router(eventos.router, prefix=API)
    app.include_router(mensagens.router, prefix=API)
    app.include_router(sugestoes.router, prefix=API)
    app.include_router(admin.router, prefix=API)
    app.include_router(arquivos.router, prefix=API)

    # A SPA é montada **depois** dos routers: a rota curinga do front não pode engolir
    # `/api/v1/...`. Sem build (`web/dist` ausente) nada é montado e a API segue sozinha.
    raiz_do_build = pasta_dist(Path(str(getattr(config, "raiz", ".") or ".")))
    app.state.tem_spa = montar_estaticos(app, raiz_do_build)

    @app.get(f"{API}/saude")
    def saude() -> dict:
        """Público: só o suficiente para saber que o servidor está de pé."""
        return {
            "ok": True,
            "versao": __version__,
            "schema": banco.versao(),
            "espaco_disco_gb": _disco_gb(config),
            "spa": bool(getattr(app.state, "tem_spa", False)),
        }

    return app


def _disco_gb(config: object | None) -> float | None:
    import shutil

    raiz = Path(str(getattr(config, "raiz", ".") or "."))
    try:
        return round(shutil.disk_usage(raiz).free / (1024**3), 1)
    except OSError:
        return None


def _dono_do_projeto(banco: Banco, projeto_id: str) -> str:
    """Usuário dono do projeto — é ele que vai como sessão do worker do núcleo."""
    con = banco.conectar()
    try:
        linha = con.execute(
            "SELECT usuario_id FROM projetos WHERE id = ?", (projeto_id,)
        ).fetchone()
    finally:
        con.close()
    return linha["usuario_id"] if linha else "sistema"


def pool_de(cfg, banco: Banco, *, cmd_base: list[str] | None = None):
    """Constrói o pool de workers do núcleo (W2) com o ambiente do `servidor.env`.

    Sem isto o app sobe sem worker e todo chat responde `SV-240`. O ambiente do filho
    carrega **só** o que o núcleo precisa: as chaves do arquivo de segredos e a configuração
    do provedor de IA (9Router / `openai_compat`, W5-16); nada de `os.environ` do servidor.
    """
    from .ponte import pool as pool_mod
    from .ponte.worker import montar_env

    segredos = {nome: valor for nome, valor in (cfg.segredos_lidos or {}).items() if valor}
    # Configuração do provedor: não é segredo, mas também não vem do ambiente do filho.
    provedor = {
        "MAPASFACIL_PROVEDOR": cfg.provedor,
        "MAPASFACIL_PROVEDOR_URL": cfg.provedor_url,
        "MAPASFACIL_MODELO_CHAT": cfg.modelo_chat,
        "MAPASFACIL_MODELO_RAPIDO": cfg.modelo_rapido,
        "MAPASFACIL_MODELO_VISAO": cfg.modelo_visao,
        "MAPASFACIL_RACIOCINIO": cfg.raciocinio,
    }

    def env_por_projeto(projeto_id: str, raiz_projeto) -> dict:
        return montar_env(
            projeto_raiz=raiz_projeto,
            usuario_id=_dono_do_projeto(banco, projeto_id),
            segredos=segredos,
            vagas_dir=cfg.vagas,
            max_jobs=cfg.max_jobs,
            extra=provedor,
        )

    return pool_mod.Pool(
        raiz_projetos=cfg.projetos,
        cmd_base=cmd_base or [str(cfg.python_nucleo), "-m", "mapasfacil_nucleo", "stdio"],
        max_workers=cfg.max_workers,
        timeout_req_s=float(cfg.timeout_req_s),
        worker_ocioso_s=float(cfg.worker_ocioso_s),
        env_por_projeto=env_por_projeto,
    )


def app_do_ambiente() -> FastAPI:
    """App de produção: lê a config do ambiente, migra o banco e sobe o pool de workers."""
    from . import config as config_mod

    cfg = config_mod.carregar()
    banco = Banco(cfg.banco)
    banco.migrar()
    return create_app(
        banco=banco,
        admin_email=cfg.admin_email,
        origem=cfg.url_publica,
        config=cfg,
        pool=pool_de(cfg, banco),
    )


__all__ = ["create_app", "app_do_ambiente", "pool_de", "json"]
