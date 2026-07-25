from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from mapasfacil_nucleo import doctor
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.motores.nativo import gerar_mapa
from mapasfacil_nucleo.protocolo import (
    Roteador,
    envelope_erro,
    novo_id,
    parsear_linha,
    serializar_linha,
)
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace.recibo_car import parsear as parsear_recibo


def criar_roteador() -> Roteador:
    roteador = Roteador()
    roteador.registrar("doctor.rodar", lambda _params: doctor.rodar())
    roteador.registrar("mapspec.validar", _handler_mapspec_validar)
    roteador.registrar("workspace.abrir", _handler_workspace_abrir)
    roteador.registrar("workspace.reindexar", _handler_workspace_reindexar)
    roteador.registrar("workspace.inspecionar", _handler_workspace_inspecionar)
    roteador.registrar("car.ler_recibo", _handler_car_ler_recibo)
    roteador.registrar("mapa.gerar", _handler_mapa_gerar)
    roteador.registrar("ping", lambda _params: {"pong": True})
    return roteador


def _handler_mapspec_validar(params: dict[str, Any]) -> dict[str, Any]:
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    fontes = params.get("fontes_locais")
    fontes_locais = frozenset(fontes) if isinstance(fontes, list) else None
    estado = workspace_servico.estado_atual()
    if fontes_locais is None and estado and estado.indice.get("fontes_locais"):
        fontes_locais = frozenset(estado.indice["fontes_locais"])
    return validar(mapspec, fontes_locais=fontes_locais)


def _handler_workspace_abrir(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if not isinstance(caminho, str) or not caminho:
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' é obrigatório.")
    return workspace_servico.abrir(caminho)


def _handler_workspace_reindexar(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if caminho is not None and not isinstance(caminho, str):
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' inválido.")
    return workspace_servico.reindexar(caminho)


def _handler_workspace_inspecionar(params: dict[str, Any]) -> dict[str, Any]:
    arquivo = params.get("arquivo")
    if not isinstance(arquivo, str) or not arquivo:
        raise ErroNucleo("NU-041", "Parâmetro 'arquivo' é obrigatório.")
    return workspace_servico.inspecionar(arquivo)


def _handler_car_ler_recibo(params: dict[str, Any]) -> dict[str, Any]:
    pdf = params.get("pdf")
    if not isinstance(pdf, str) or not pdf:
        raise ErroNucleo("NU-041", "Parâmetro 'pdf' é obrigatório.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de ler o recibo.")
    caminho = estado.guard.resolver(pdf)
    dados = parsear_recibo(caminho).para_dict()
    assert "cpf" not in dados
    return dados


def _handler_mapa_gerar(params: dict[str, Any]) -> dict[str, Any]:
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de gerar o mapa.")
    fontes_idx = {
        item["id_local"]: item["caminho"] for item in estado.indice.get("shapefiles", [])
    }
    return gerar_mapa(mapspec, estado.guard, fontes_idx)


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
