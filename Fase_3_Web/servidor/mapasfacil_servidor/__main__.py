"""CLI do servidor.

    python -m mapasfacil_servidor --version
    python -m mapasfacil_servidor serve
    python -m mapasfacil_servidor migrar
    python -m mapasfacil_servidor conta criar|listar|bloquear|desbloquear
    python -m mapasfacil_servidor limpar-lixeira
    python -m mapasfacil_servidor sonda-saude

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


def _banco_migrado():
    from .db import Banco

    cfg = carregar()
    banco = Banco(cfg.banco)
    banco.migrar()
    return cfg, banco


def cmd_serve() -> int:
    cfg = carregar()
    from .app import app_do_ambiente

    import uvicorn

    uvicorn.run(app_do_ambiente(), host=cfg.host, port=cfg.porta, log_level="info")
    return 0


def cmd_migrar() -> int:
    cfg, banco = _banco_migrado()
    print(f"schema na versão {banco.versao()} em {cfg.banco}")
    return 0


def cmd_limpar_lixeira() -> int:
    from . import manutencao

    cfg, banco = _banco_migrado()
    resultado = manutencao.limpar_lixeira(banco, cfg, dias=30)
    print(f"projetos apagados: {resultado['projetos']} · uploads expirados: {resultado['uploads']}")
    return 0


def cmd_conta(args: argparse.Namespace) -> int:
    """W3-23: contas pela CLI, sem passar pela web."""
    from .auth import contas, senhas

    cfg, banco = _banco_migrado()
    con = banco.conectar()
    try:
        if args.acao == "criar":
            if not args.email or not args.nome:
                raise ErroServidor("SV-016", "Informe --email e --nome.", status_http=400)
            temporaria = args.senha or senhas.gerar_senha_temporaria()
            usuario = contas.criar(
                con,
                nome=args.nome,
                email=args.email,
                senha=temporaria,
                papel="admin" if args.admin else "usuario",
                trocar_senha=not args.sem_trocar,
                admin_email=cfg.admin_email,
            )
            print(f"{usuario.id}  {usuario.email}  papel={usuario.papel}")
            if not args.senha:
                # Aparece uma vez; não é gravada em claro em lugar nenhum.
                print(f"senha temporária (mostre uma vez): {temporaria}")
            return 0

        if args.acao == "listar":
            for usuario in contas.listar(con):
                estado = "ativo" if usuario.ativo else "bloqueado"
                print(f"{usuario.id}  {usuario.email}  {usuario.papel}  {estado}")
            return 0

        if args.acao in {"bloquear", "desbloquear"}:
            if not args.email:
                raise ErroServidor("SV-016", "Informe --email.", status_http=400)
            usuario = contas.buscar_por_email(con, args.email)
            if usuario is None:
                raise ErroServidor("SV-034", "Usuário não encontrado.", status_http=404)
            atualizado = contas.bloquear(
                con,
                usuario_id=usuario.id,
                ativo=args.acao == "desbloquear",
                autor_id=None,
            )
            print(f"{atualizado.email}: {'ativo' if atualizado.ativo else 'bloqueado'}")
            return 0
    finally:
        con.close()

    raise NaoImplementado(f"conta {args.acao}", "W3")


def cmd_sonda_saude() -> int:
    """W12-04: sonda o `/saude` do app e só grita depois de 3 falhas seguidas.

    Uma falha isolada é deploy, restart ou WAL checkpoint — alerta em cima disso vira ruído e o
    alarme perde o valor. O contador fica em `logs/.saude_falhas` e o alerta em
    `logs/alertas.log` (JSON por linha, igual ao resto dos logs).
    """
    import json
    import time
    import urllib.error
    import urllib.request

    cfg = carregar()
    logs = cfg.logs
    logs.mkdir(parents=True, exist_ok=True)
    contador = logs / ".saude_falhas"
    alertas = logs / "alertas.log"
    url = f"http://{cfg.host}:{cfg.porta}/api/v1/saude"

    def _anotar(nivel: str, mensagem: str) -> None:
        linha = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "nivel": nivel,
            "codigo": "SV-SAUDE",
            "mensagem": mensagem,
            "url": url,
        }
        with alertas.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + chr(10))

    try:
        with urllib.request.urlopen(url, timeout=10) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
        contador.write_text("0", encoding="utf-8")
        print(f"ok: {corpo.get('estado')} versao={corpo.get('versao')}")
        return 0
    except (urllib.error.URLError, OSError, ValueError) as exc:
        falhas = 0
        if contador.is_file():
            try:
                falhas = int(contador.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                falhas = 0
        falhas += 1
        contador.write_text(str(falhas), encoding="utf-8")
        print(f"falha {falhas}/3: {exc}", file=sys.stderr)
        if falhas >= 3:
            _anotar("erro", f"{falhas} falhas seguidas na sonda de saúde: {exc}")
            print("alerta gravado em logs/alertas.log", file=sys.stderr)
            return 1
        return 0


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
    sub.add_parser(
        "sonda-saude",
        help="consulta /saude e grava alerta em logs/alertas.log após 3 falhas seguidas",
    )

    conta = sub.add_parser("conta", help="administração de contas pela CLI")
    conta.add_argument("acao", choices=["criar", "listar", "bloquear", "desbloquear"])
    conta.add_argument("--email", help="e-mail da conta")
    conta.add_argument("--nome", help="nome (só no criar)")
    conta.add_argument("--senha", help="senha; sem ela a CLI gera temporária e mostra uma vez")
    conta.add_argument("--admin", action="store_true", help="cria com papel admin")
    conta.add_argument(
        "--sem-trocar",
        action="store_true",
        help="não obriga troca de senha no primeiro acesso",
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
        if args.comando == "sonda-saude":
            return cmd_sonda_saude()
        if args.comando == "conta":
            return cmd_conta(args)
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
