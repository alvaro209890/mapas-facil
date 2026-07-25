from __future__ import annotations

import sys
from typing import Any, TextIO

from mapasfacil_nucleo import doctor
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.protocolo import (
    Roteador,
    envelope_erro,
    envelope_res,
    novo_id,
    parsear_linha,
    serializar_linha,
)


def criar_roteador() -> Roteador:
    roteador = Roteador()
    roteador.registrar("doctor.rodar", lambda _params: doctor.rodar())
    roteador.registrar("mapspec.validar", _handler_mapspec_validar)
    roteador.registrar("ping", lambda _params: {"pong": True})
    return roteador


def _handler_mapspec_validar(params: dict[str, Any]) -> dict[str, Any]:
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    fontes = params.get("fontes_locais")
    fontes_locais = frozenset(fontes) if isinstance(fontes, list) else None
    return validar(mapspec, fontes_locais=fontes_locais)


def processar_linha(linha: str, roteador: Roteador | None = None) -> str:
    roteador = roteador or criar_roteador()
    id_req = novo_id()
    try:
        mensagem = parsear_linha(linha)
        id_req = mensagem.get("id", id_req)
        resposta = roteador.despachar(mensagem)
    except ErroNucleo as exc:
        resposta = envelope_erro(id_req, exc)
    return serializar_linha(resposta) + "\n"


def loop_ndjson(
    entrada: TextIO | None = None,
    saida: TextIO | None = None,
    roteador: Roteador | None = None,
) -> None:
    entrada = entrada or sys.stdin
    saida = saida or sys.stdout
    roteador = roteador or criar_roteador()
    for linha in entrada:
        linha = linha.strip()
        if not linha:
            continue
        saida.write(processar_linha(linha, roteador))
        saida.flush()


def main_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sidecar Mapas Fácil")
    sub = parser.add_subparsers(dest="comando")

    sub.add_parser("stdio", help="Loop NDJSON (padrão do Electron)")
    doctor_parser = sub.add_parser("doctor", help="Diagnóstico do ambiente")
    doctor_parser.add_argument("--json", action="store_true", help="Saída JSON")

    args = parser.parse_args()
    if args.comando in (None, "stdio"):
        loop_ndjson()
        return
    if args.comando == "doctor":
        resultado = doctor.rodar()
        if args.json:
            import json

            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            print(f"Mapas Fácil núcleo {resultado['nucleo']} — {resultado['so']}")
            print(f"Python {resultado['python']}")
            print(f"ogr2ogr: {resultado['gdal']['ogr2ogr'] or 'não encontrado'}")
            print(f"Pronto para MXD: {resultado['pronto_para_mxd']}")
        return
    parser.error(f"Comando desconhecido: {args.comando}")


if __name__ == "__main__":
    main_cli()
