from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import pytest

validar_mod = importlib.import_module("mapasfacil_nucleo.mapspec.validar")
validar = validar_mod.validar


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


def test_aviso_template_sem_sha256(mapspec_canonico: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    # 25/25 templates do MANIFEST já têm sha256 (2026-07-29);
    # monkeypatch simula um template sem sha256 (caso a_preparar).
    monkeypatch.setattr(
        validar_mod,
        "_template_ids",
        lambda: frozenset({"tipologia_paisagem"}),
    )
    monkeypatch.setattr(
        validar_mod,
        "_templates_por_id",
        lambda: {"tipologia_paisagem": {"id": "tipologia_paisagem", "status": "a_preparar"}},
    )
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


def test_mapspec_aceita_imoveis_multiplo_valido(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["imoveis"] = [
        {
            "id": "imovel_1",
            "nome": "Fazenda Boa Vista",
            "car": "MT-5107008-1111",
            "matricula": "1234",
            "area": 250.5,
            "atp": "CAR/ATP.shp",
            "principal": True,
        },
        {
            "id": "imovel_2",
            "nome": "Fazenda Santa Maria",
            "car": "MT-5107008-2222",
            "matricula": "5678",
            "area": 180.0,
            "atp": "CAR/LOTE_45.shp",
            "principal": False,
        },
    ]
    spec["camadas"][0]["imovel_id"] = "imovel_1"
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is True
    assert resultado["erros"] == []


def test_mapspec_rejeita_imoveis_com_ids_duplicados(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["imoveis"] = [
        {"id": "imovel_1", "nome": "Fazenda 1", "principal": True},
        {"id": "imovel_1", "nome": "Fazenda 2", "principal": False},
    ]
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-230" for e in resultado["erros"])


def test_mapspec_rejeita_imoveis_com_multiplos_principais(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["imoveis"] = [
        {"id": "imovel_1", "nome": "Fazenda 1", "principal": True},
        {"id": "imovel_2", "nome": "Fazenda 2", "principal": True},
    ]
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-231" for e in resultado["erros"])


def test_mapspec_rejeita_camada_com_imovel_id_inexistente(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["imoveis"] = [
        {"id": "imovel_1", "nome": "Fazenda 1", "principal": True},
    ]
    spec["camadas"][0]["imovel_id"] = "imovel_fantasma"
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-232" for e in resultado["erros"])


def test_mapspec_aceita_layout_spec_valido(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    caminho_layout = Path(__file__).resolve().parents[3] / "shared" / "layouts" / "harmonia_dinamica_retrato.json"
    spec["layout_spec"] = json.loads(caminho_layout.read_text(encoding="utf-8"))
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is True
    assert resultado["erros"] == []


def test_mapspec_rejeita_layout_spec_invalido(mapspec_canonico: dict) -> None:
    spec = copy.deepcopy(mapspec_canonico)
    spec["layout_spec"] = {
        "contract_version": 1,
        "perfil": "harmonia",
        "orientacao": "retrato",
    }
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] == "NU-234" for e in resultado["erros"])
