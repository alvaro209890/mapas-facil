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


def _escrever(mensagem: dict[str, Any]) -> None:
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

        atraso = float(passo.get("atraso", 0) or 0)
        if atraso:
            time.sleep(atraso)

        for evento in passo.get("eventos", []):
            time.sleep(float(evento.get("atraso", 0) or 0))
            _escrever(
                protocolo.envelope_evt(id_req, evento["evento"], evento.get("dados") or {})
            )

        if "erro" in passo:
            _escrever(protocolo.envelope_erro(id_req, passo["erro"]))
        else:
            _escrever(protocolo.envelope_res(id_req, passo.get("resultado") or {}))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
