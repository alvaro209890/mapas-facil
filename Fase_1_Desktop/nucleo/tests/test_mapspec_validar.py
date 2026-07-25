from __future__ import annotations

import copy

import pytest

from mapasfacil_nucleo.mapspec.validar import validar


def test_exemplo_canonico_valido(mapspec_canonico: dict) -> None:
    resultado = validar(
        mapspec_canonico,
        fontes_locais=frozenset({"ATP", "AVN", "AUAS"}),
    )
    assert resultado["valido"] is True
    assert resultado["erros"] == []


def test_rejeita_camada_fora_do_catalogo(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["camadas"][3]["fonte"] = "catalogo.camada_inexistente_xyz"
    resultado = validar(spec)
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-210" for e in resultado["erros"])


def test_rejeita_escala_invalida(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["escala"] = 12345
    resultado = validar(spec)
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-220" for e in resultado["erros"])


def test_aceita_escala_auto(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["escala"] = "auto"
    resultado = validar(
        spec,
        fontes_locais=frozenset({"ATP", "AVN", "AUAS"}),
    )
    assert resultado["valido"] is True


def test_rejeita_schema_quebrado(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    del spec["titulo"]
    resultado = validar(spec)
    assert resultado["valido"] is False
    assert resultado["erros"][0]["codigo"] == "NU-201"


def test_rejeita_fonte_local_ausente(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    resultado = validar(spec, fontes_locais=frozenset({"ATP"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-212" for e in resultado["erros"])


def test_rejeita_nome_base_com_acento(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["saida"]["nome_base"] = "Dinâmica_2026"
    resultado = validar(
        spec,
        fontes_locais=frozenset({"ATP", "AVN", "AUAS"}),
    )
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-215" for e in resultado["erros"])
