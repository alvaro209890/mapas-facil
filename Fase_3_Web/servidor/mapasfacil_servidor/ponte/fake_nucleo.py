"""Núcleo falso — fala o protocolo real e obedece a um roteiro NDJSON (W-04).

Usado pelos testes do servidor para exercitar worker, pool e stream **sem** GDAL,
rede ou IA. Cada linha do roteiro descreve uma resposta:

    {"metodo": "doctor.rodar", "resultado": {"modo": "servidor"}}
    {"metodo": "mapa.gerar",
     "eventos": [{"atraso": 0.01, "evento": "job.progresso", "dados": {"pct": 50}}],
     "resultado": {"ok": true}}
    {"metodo": "mapa.gerar", "erro": {"codigo": "NU-500", "mensagem": "falhou"}}
    {"metodo": "chat.enviar", "morrer": true}          # simula kill -9
    {"metodo": "chat.enviar", "atraso": 5, "resultado": {}}

Uso: `python -m mapasfacil_servidor.ponte.fake_nucleo --roteiro <arquivo.ndjson>`
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import protocolo


def carregar_roteiro(caminho: Path) -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        texto = bruta.strip()
        if not texto or texto.startswith("#"):
            continue
        linhas.append(json.loads(texto))
    return linhas


_TRAVA_SAIDA = threading.Lock()


def _escrever(mensagem: dict[str, Any]) -> None:
    with _TRAVA_SAIDA:
        sys.stdout.write(protocolo.serializar_linha(mensagem) + "\n")
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fake_nucleo")
    parser.add_argument("--roteiro", required=True)
    parser.add_argument("--echo-stderr", default="")
    args = parser.parse_args(argv)

    roteiro = carregar_roteiro(Path(args.roteiro))
    if args.echo_stderr:
        print(args.echo_stderr, file=sys.stderr, flush=True)

    threads: list[threading.Thread] = []
    for linha in sys.stdin:
        texto = linha.strip()
        if not texto:
            continue
        req = protocolo.parsear_linha(texto)
        if req.get("tipo") != "req":
            continue
        metodo = req.get("metodo")
        id_req = req.get("id", "")

        passo = next((p for p in roteiro if p.get("metodo") == metodo), None)
        if passo is None:
            _escrever(
                protocolo.envelope_erro(
                    id_req,
                    {"codigo": "NU-002", "mensagem": f"Método desconhecido no roteiro: {metodo}"},
                )
            )
            continue

        if passo.get("morrer"):
            sys.exit(9)

        # Igual ao núcleo real (A10): os métodos longos correm numa thread e o resto do
        # protocolo continua sendo atendido enquanto isso.
        if metodo in METODOS_EM_BACKGROUND:
            thread = threading.Thread(target=_responder, args=(passo, id_req), daemon=True)
            threads.append(thread)
            thread.start()
        else:
            _responder(passo, id_req)

    # stdin fechou: termina os pedidos longos antes de sair (o núcleo real faz o mesmo).
    for thread in threads:
        thread.join(timeout=600)
    return 0


METODOS_EM_BACKGROUND = frozenset({"mapa.gerar", "analise.executar", "chat.enviar"})


def _responder(passo: dict[str, Any], id_req: str) -> None:
    atraso = float(passo.get("atraso", 0) or 0)
    if atraso:
        time.sleep(atraso)

    for evento in passo.get("eventos", []):
        time.sleep(float(evento.get("atraso", 0) or 0))
        _escrever(protocolo.envelope_evt(id_req, evento["evento"], evento.get("dados") or {}))

    if "erro" in passo:
        _escrever(protocolo.envelope_erro(id_req, passo["erro"]))
    else:
        _escrever(protocolo.envelope_res(id_req, passo.get("resultado") or {}))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
