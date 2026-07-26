# Carga e validação de shared/galeria/modelos.json (F1-15 D3).

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import jsonschema

from mapasfacil_nucleo.config import caminho_shared
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.motores import manifesto

_LOG = logging.getLogger("mapasfacil.galeria")


@lru_cache(maxsize=1)
def carregar_galeria() -> dict[str, Any]:
    caminho = caminho_shared("galeria", "modelos.json")
    schema_path = caminho_shared("galeria", "schema.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    with schema_path.open(encoding="utf-8") as fh:
        schema = json.load(fh)
    try:
        jsonschema.validate(dados, schema)
    except jsonschema.ValidationError as exc:
        raise ErroNucleo(
            "NU-234",
            f"modelos.json inválido: {exc.message}",
            {"caminho": str(caminho)},
        ) from exc

    ids_template = {t.get("id") for t in manifesto.carregar().get("templates", [])}
    modelos_ok: list[dict[str, Any]] = []
    for modelo in dados.get("modelos", []):
        template_id = modelo.get("template")
        if template_id not in ids_template:
            _LOG.error(
                "NU-231 · modelo %s aponta para template ausente do MANIFEST: %s",
                modelo.get("id"),
                template_id,
            )
            continue
        preview = caminho_shared("galeria", modelo.get("preview", ""))
        if not preview.is_file():
            _LOG.warning("preview ausente para %s: %s", modelo.get("id"), preview)
        modelos_ok.append(modelo)

    return {
        "galeria_version": dados["galeria_version"],
        "contract_version": dados["contract_version"],
        "modelos": modelos_ok,
    }


def obter_modelo(modelo_id: str) -> dict[str, Any]:
    for modelo in carregar_galeria()["modelos"]:
        if modelo["id"] == modelo_id:
            return modelo
    raise ErroNucleo(
        "NU-230",
        f"Modelo de galeria inexistente: {modelo_id}",
        {"modelo_id": modelo_id},
    )


def limpar_cache() -> None:
    carregar_galeria.cache_clear()
