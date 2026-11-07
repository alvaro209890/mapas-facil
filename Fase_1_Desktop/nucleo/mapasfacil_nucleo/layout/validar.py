"""Validação de LayoutSpec contra o schema oficial."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from mapasfacil_nucleo.config import raiz_repositorio
from .modelo import LayoutSpec


@lru_cache(maxsize=1)
def _obter_schema() -> dict[str, Any]:
    caminho = raiz_repositorio() / "shared" / "schemas" / "layoutspec.schema.json"
    if not caminho.is_file():
        raise FileNotFoundError(f"Schema do LayoutSpec não encontrado: {caminho}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def validar(dados: dict[str, Any] | LayoutSpec) -> dict[str, Any]:
    """Valida um LayoutSpec contra o schema oficial."""
    dicionario = dados.para_dict() if isinstance(dados, LayoutSpec) else dados
    schema = _obter_schema()
    validator = Draft202012Validator(schema)

    erros: list[str] = []
    for erro in sorted(validator.iter_errors(dicionario), key=lambda e: e.path):
        caminho = ".".join(str(p) for p in erro.path) or "(raiz)"
        erros.append(f"{caminho}: {erro.message}")

    if not erros:
        pagina = dicionario["dimensoes_mm"]
        largura, altura = pagina["largura"], pagina["altura"]
        caixas = dicionario["elementos"]
        if not all(math.isfinite(v) for v in (largura, altura)):
            erros.append("dimensoes_mm: dimensões devem ser finitas")
        for nome, caixa in caixas.items():
            valores = [caixa[c] for c in ("x0", "y0", "x1", "y1")]
            if not all(math.isfinite(v) for v in valores):
                erros.append(f"elementos.{nome}: coordenadas devem ser finitas")
                continue
            x0, y0, x1, y1 = valores
            if x1 <= x0 or y1 <= y0:
                erros.append(f"elementos.{nome}: caixa invertida ou sem área")
            if x0 < 0 or y0 < 0 or x1 > largura + 0.05 or y1 > altura + 0.05:
                erros.append(f"elementos.{nome}: caixa fora da página")
        mapa, titulo = caixas["mapa"], caixas["titulo"]
        if (titulo["x0"] < mapa["x0"] - 0.15 or titulo["y0"] < mapa["y0"] - 0.15
                or titulo["x1"] > mapa["x1"] + 0.15 or titulo["y1"] > mapa["y1"] + 0.15):
            erros.append("elementos.titulo: título deve estar dentro do quadro do mapa")

    return {
        "valido": len(erros) == 0,
        "erros": erros,
    }
