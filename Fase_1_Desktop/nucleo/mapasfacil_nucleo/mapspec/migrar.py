"""Migração do `MapSpec` para o contrato atual (D36, W1-12).

`contract_version` 3 acrescenta o bloco obrigatório `folha` (`formato`, `orientacao`,
`escala_elementos`). O v2 não tinha o campo — mas a informação sempre existiu no
`formato_pagina` do template `.mxd`, então a migração é determinística: lê o template no
MANIFEST e monta o bloco. Spec gravado pelo desktop continua abrindo; spec novo nasce v3.
"""

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.motores import folhas

CONTRACT_ATUAL = 3

# Versões que esta migração entende. Contrato mais novo que isto é erro, não chute.
CONTRACT_MINIMO = 1


def _folha_do_spec(mapspec: dict[str, Any]) -> dict[str, Any]:
    """Bloco `folha` a partir do template; A4 retrato quando o template é desconhecido."""
    template = mapspec.get("template")
    if isinstance(template, str) and template:
        derivada = folhas.folha_do_template(template)
        if derivada:
            return derivada
    return folhas.folha_padrao()


def migrar(mapspec: dict[str, Any]) -> dict[str, Any]:
    """Devolve uma **cópia** do spec no contrato atual. Nunca altera o original."""
    if not isinstance(mapspec, dict):
        return mapspec  # type: ignore[return-value]

    copia = dict(mapspec)
    versao = copia.get("contract_version")

    if versao == CONTRACT_ATUAL:
        if not isinstance(copia.get("folha"), dict):
            copia["folha"] = _folha_do_spec(copia)
        return copia

    if not isinstance(versao, int) or versao < CONTRACT_MINIMO:
        # Sem versão legível o validador precisa reclamar — devolve como está.
        return copia

    copia["contract_version"] = CONTRACT_ATUAL
    if not isinstance(copia.get("folha"), dict):
        copia["folha"] = _folha_do_spec(copia)
    return copia


def precisa_migrar(mapspec: dict[str, Any]) -> bool:
    return isinstance(mapspec, dict) and mapspec.get("contract_version") != CONTRACT_ATUAL
