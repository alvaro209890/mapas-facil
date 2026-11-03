"""CLI do servidor.

    python -m mapasfacil_servidor --version
    python -m mapasfacil_servidor serve
    python -m mapasfacil_servidor migrar
    python -m mapasfacil_servidor conta criar|listar|bloquear|desbloquear
    python -m mapasfacil_servidor limpar-lixeira

A superfície nasce no W0; o corpo de cada comando chega no marco dono
(`migrar`/`limpar-lixeira` no W12-04, `conta` no W3-23). Comando sem corpo
responde `SV-098` e sai com código 3 — nunca finge ter feito.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__
from .config import carregar
from .erros import ErroServidor, NaoImplementado


def _imprimir_erro(erro: ErroServidor) -> None:
    print(f"{erro.codigo}: {erro.mensagem}", file=sys.stderr)
    if erro.porque:
        print(f"  porque: {erro.porque}", file=sys.stderr)
    if erro.o_que_fazer:
        print(f"  o que fazer: {erro.o_que_fazer}", file=sys.stderr)


def cmd_serve() -> int:
    cfg = carregar()
    try:
        from .app import criar_app  # chega no W3
    except ImportError as exc:  # pragma: no cover - caminho do W0
        raise NaoImplementado("serve", "W3") from exc

    import uvicorn

    uvicorn.run(criar_app(cfg), host=cfg.host, port=cfg.porta, log_level="info")
    return 0


def cmd_migrar() -> int:
    carregar()
    raise NaoImplementado("migrar", "W12 (W12-04)")


def cmd_limpar_lixeira() -> int:
    carregar()
    raise NaoImplementado("limpar-lixeira", "W12 (W12-04)")


def cmd_conta(acao: str) -> int:
    carregar()
    raise NaoImplementado(f"conta {acao}", "W3 (W3-23)")


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mapasfacil_servidor",
        description="Backend web do Mapas Fácil (Fase 3).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mapasfacil_servidor {__version__}",
    )
    sub = parser.add_subparsers(dest="comando")

    sub.add_parser("serve", help="sobe a API + SPA (127.0.0.1 por padrão)")
    sub.add_parser("migrar", help="aplica as migrações do SQLite")
    sub.add_parser("limpar-lixeira", help="apaga lixeira > 30 dias e uploads expirados")

    conta = sub.add_parser("conta", help="administração de contas pela CLI")
    conta.add_argument(
        "acao",
        choices=["criar", "listar", "bloquear", "desbloquear"],
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = montar_parser()
    args = parser.parse_args(argv)

    if not args.comando:
        parser.print_help()
        return 0

    try:
        if args.comando == "serve":
            return cmd_serve()
        if args.comando == "migrar":
            return cmd_migrar()
        if args.comando == "limpar-lixeira":
            return cmd_limpar_lixeira()
        if args.comando == "conta":
            return cmd_conta(args.acao)
    except NaoImplementado as erro:
        _imprimir_erro(erro)
        return 3
    except ErroServidor as erro:
        _imprimir_erro(erro)
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
