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


def test_rejeita_crs_geografico(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["crs"] = "EPSG:4674"
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-221" for e in resultado["erros"])


def test_rejeita_pasta_absoluta(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["saida"]["pasta"] = "/tmp"
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-224" for e in resultado["erros"])


def test_rejeita_municipio_vazio_com_minimapa(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["imovel"]["municipio"]["nome"] = ""
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] in {"NU-201", "NU-222"} for e in resultado["erros"])


def test_rejeita_metadado_vazio(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["metadados"][0]["valor"] = ""
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-223" for e in resultado["erros"])


def test_aviso_template_sem_sha256(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["template"] = "tipologia_paisagem"
    resultado = validar(
        spec,
        fontes_locais=frozenset({"ATP", "AVN", "AUAS"}),
    )
    assert resultado["valido"] is True
    assert any(a["codigo"] == "AG-030" for a in resultado["avisos"])


def test_aceita_operador_diferente(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["camadas"][3]["filtro"]["operador"] = "<>"
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is True
