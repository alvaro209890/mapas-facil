from __future__ import annotations

import copy

from mapasfacil_nucleo.mapspec.diff import diff


def test_diff_sem_mudancas(mapspec_canonico: dict) -> None:
    resultado = diff(mapspec_canonico, copy.deepcopy(mapspec_canonico))
    assert resultado["total"] == 0
    assert resultado["operacoes"] == []


def test_diff_altera_titulo(mapspec_canonico: dict) -> None:
    depois = copy.deepcopy(mapspec_canonico)
    depois["titulo"] = "Dinâmica 2025"
    resultado = diff(mapspec_canonico, depois)
    assert resultado["total"] == 1
    assert resultado["operacoes"][0]["op"] == "alterar"
    assert resultado["operacoes"][0]["caminho"] == "titulo"


def test_diff_camadas_por_id(mapspec_canonico: dict) -> None:
    depois = copy.deepcopy(mapspec_canonico)
    depois["camadas"] = [c for c in depois["camadas"] if c["id"] != "avn"]
    resultado = diff(mapspec_canonico, depois)
    assert any(op["op"] == "remover" and op["caminho"] == "camadas/avn" for op in resultado["operacoes"])


def test_diff_adiciona_camada(mapspec_canonico: dict) -> None:
    depois = copy.deepcopy(mapspec_canonico)
    depois["camadas"].append(
        {
            "id": "nova",
            "fonte": "local.ATP",
            "estilo": "perimetro_imovel",
            "ordem": 5,
        }
    )
    resultado = diff(mapspec_canonico, depois)
    assert any(op["op"] == "adicionar" and op["caminho"] == "camadas/nova" for op in resultado["operacoes"])
