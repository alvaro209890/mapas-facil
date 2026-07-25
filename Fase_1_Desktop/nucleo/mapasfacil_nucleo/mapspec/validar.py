from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from mapasfacil_nucleo.config import ESCALAS_PERMITIDAS, caminho_shared
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import nome_base_ascii_valido

ESTILOS_PERMITIDOS: frozenset[str] = frozenset(
    {
        "perimetro_imovel",
        "avn",
        "ac",
        "auas",
        "limite_municipal",
        "tipologia",
        "embargo",
        "ti",
        "uc",
    }
)

OPERADORES_FILTRO = frozenset({"=", "!=", "IN", "LIKE"})


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    caminho = caminho_shared("schemas", "mapspec.schema.json")
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _catalogo_ids() -> frozenset[str]:
    caminho = caminho_shared("catalog", "camadas.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    return frozenset(item["id"] for item in dados.get("camadas", []))


@lru_cache(maxsize=1)
def _template_ids() -> frozenset[str]:
    caminho = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    return frozenset(item["id"] for item in dados.get("templates", []))


def _erro(codigo: str, mensagem: str, campo: str | None = None) -> dict[str, str]:
    item = {"codigo": codigo, "mensagem": mensagem}
    if campo:
        item["campo"] = campo
    return item


def validar_schema(mapspec: dict[str, Any]) -> list[dict[str, str]]:
    validator = Draft202012Validator(_schema())
    erros: list[dict[str, str]] = []
    for err in sorted(validator.iter_errors(mapspec), key=lambda e: list(e.path)):
        caminho = "/".join(str(p) for p in err.path) or "(raiz)"
        erros.append(_erro("NU-201", f"{caminho}: {err.message}", caminho))
    return erros


def validar_regras(
    mapspec: dict[str, Any],
    *,
    fontes_locais: frozenset[str] | None = None,
) -> list[dict[str, str]]:
    erros: list[dict[str, str]] = []

    template = mapspec.get("template")
    if isinstance(template, str) and template not in _template_ids():
        erros.append(_erro("NU-205", f"Template desconhecido: {template}", "template"))

    escala = mapspec.get("escala")
    if escala is not None and escala != "auto":
        if not isinstance(escala, int) or escala not in ESCALAS_PERMITIDAS:
            erros.append(
                _erro(
                    "NU-220",
                    f"Escala {escala!r} não está na lista permitida.",
                    "escala",
                )
            )

    crs = mapspec.get("crs")
    if isinstance(crs, str) and crs.upper().startswith("EPSG:4326"):
        erros.append(_erro("NU-221", "CRS geográfico não é permitido em crs.", "crs"))

    camadas = mapspec.get("camadas") or []
    for idx, camada in enumerate(camadas):
        prefixo = f"camadas[{idx}]"
        estilo = camada.get("estilo")
        if isinstance(estilo, str) and estilo not in ESTILOS_PERMITIDOS:
            erros.append(
                _erro(
                    "NU-211",
                    f"Estilo desconhecido: {estilo}",
                    f"{prefixo}/estilo",
                )
            )

        fonte = camada.get("fonte")
        if isinstance(fonte, str):
            if fonte.startswith("catalogo."):
                cat_id = fonte.split(".", 1)[1]
                if cat_id not in _catalogo_ids():
                    erros.append(
                        _erro(
                            "NU-210",
                            f"Camada de catálogo inexistente: {cat_id}",
                            f"{prefixo}/fonte",
                        )
                    )
            elif fonte.startswith("local."):
                local_id = fonte.split(".", 1)[1]
                if fontes_locais is not None and local_id not in fontes_locais:
                    erros.append(
                        _erro(
                            "NU-212",
                            f"Fonte local ausente no workspace: {local_id}",
                            f"{prefixo}/fonte",
                        )
                    )
            else:
                erros.append(
                    _erro(
                        "NU-213",
                        f"Fonte precisa ser local.* ou catalogo.*: {fonte}",
                        f"{prefixo}/fonte",
                    )
                )

        filtro = camada.get("filtro")
        if isinstance(filtro, dict):
            operador = filtro.get("operador")
            if operador not in OPERADORES_FILTRO:
                erros.append(
                    _erro(
                        "NU-214",
                        f"Operador de filtro inválido: {operador!r}",
                        f"{prefixo}/filtro/operador",
                    )
                )

    saida = mapspec.get("saida") or {}
    nome_base = saida.get("nome_base")
    if isinstance(nome_base, str) and not nome_base_ascii_valido(nome_base):
        erros.append(
            _erro(
                "NU-215",
                "saida.nome_base precisa ser ASCII sem acentos.",
                "saida/nome_base",
            )
        )

    tabela = mapspec.get("tabela")
    if isinstance(tabela, dict):
        colunas = tabela.get("colunas") or []
        for i, linha in enumerate(tabela.get("linhas") or []):
            if len(linha) != len(colunas):
                erros.append(
                    _erro(
                        "NU-216",
                        f"Linha {i} da tabela tem {len(linha)} colunas; esperado {len(colunas)}.",
                        f"tabela/linhas[{i}]",
                    )
                )

    return erros


def validar(
    mapspec: dict[str, Any],
    *,
    fontes_locais: frozenset[str] | None = None,
) -> dict[str, Any]:
    erros = validar_schema(mapspec)
    if not erros:
        erros = validar_regras(mapspec, fontes_locais=fontes_locais)
    return {
        "valido": len(erros) == 0,
        "erros": erros,
        "avisos": [],
    }


def validar_ou_erro(mapspec: dict[str, Any]) -> None:
    resultado = validar(mapspec)
    if not resultado["valido"]:
        primeiro = resultado["erros"][0]
        raise ErroNucleo(primeiro["codigo"], primeiro["mensagem"], {"erros": resultado["erros"]})
