"""Testes do pacote layout (LayoutSpec declarativo e PDF-first).

Valida:
1. Validação de schema contra shared/schemas/layoutspec.schema.json;
2. Conversão bidirecional PerfilPagina <-> LayoutSpec;
3. Carregamento de arquivos JSON e presets;
4. Resolução de layout por template e por modelo;
5. Medição de layout a partir de PDF de referência.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.motores.perfil_pagina import RETRATO, PAISAGEM, Caixa
from mapasfacil_nucleo.layout import (
    LayoutSpec,
    carregar,
    de_perfil,
    validar,
    medir,
    perfil_do_layout,
    obter_layout,
    listar_layouts,
)

_RAIZ = raiz_repositorio()


def test_validar_layout_spec_valido() -> None:
    caminho = _RAIZ / "shared" / "layouts" / "harmonia_dinamica_retrato.json"
    assert caminho.is_file()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    resultado = validar(dados)
    assert resultado["valido"] is True
    assert resultado["erros"] == []


def test_validar_layout_spec_invalido() -> None:
    dados_invalidos = {
        "versao": 1,
        # contract_version ausente
        "id": "teste",
        "nome": "Incompleto",
        "perfil": "harmonia",
        "orientacao": "retrato",
        "dimensoes_mm": {"largura": 210.0, "altura": 297.0},
        "elementos": {
            # faltam elementos obrigatorios como mapa, titulo, rosa...
            "mapa": {"x0": 7.0, "y0": 5.0, "x1": 203.5, "y1": 257.0}
        },
    }
    resultado = validar(dados_invalidos)
    assert resultado["valido"] is False
    assert len(resultado["erros"]) > 0


def test_de_perfil_e_perfil_do_layout_roundtrip() -> None:
    spec = de_perfil(RETRATO, id="dinamica_teste", nome="Teste Retrato")
    assert isinstance(spec, LayoutSpec)
    assert spec.id == "dinamica_teste"
    assert spec.orientacao == "retrato"
    assert spec.elementos["mapa"].x0 == 7.0
    assert spec.elementos["titulo"].y0 == pytest.approx(7.11, rel=1e-2)

    # Converte de volta para PerfilPagina
    perfil = perfil_do_layout(spec)
    assert perfil.largura_mm == 210.0
    assert perfil.altura_mm == 297.0
    assert perfil.mapa.x0 == 7.0
    assert perfil.mapa.y1 == 257.0
    assert perfil.titulo.y0 == pytest.approx(7.11, rel=1e-2)
    assert perfil.orientacao == "retrato"


def test_perfil_do_layout_com_folha_maior() -> None:
    spec = de_perfil(RETRATO)
    perfil_a3 = perfil_do_layout(spec, folha={"formato": "A3", "orientacao": "retrato"})
    assert perfil_a3.formato == "A3"
    assert perfil_a3.largura_mm == 297.0
    assert perfil_a3.altura_mm == 420.0
    assert perfil_a3.fator > 1.4


def test_carregar_por_id_e_por_dict() -> None:
    spec = carregar("harmonia_dinamica_retrato")
    assert spec.id == "harmonia_dinamica_retrato"
    assert spec.dimensoes_mm.largura == 210.0

    dict_spec = spec.para_dict()
    spec2 = carregar(dict_spec)
    assert spec2.id == spec.id
    assert spec2.elementos["mapa"].x1 == spec.elementos["mapa"].x1


def test_obter_layout_templates_conhecidos() -> None:
    # Template direto
    spec_ret = obter_layout("dinamica_retrato")
    assert spec_ret.orientacao == "retrato"

    spec_pais = obter_layout("tipologia_paisagem")
    assert spec_pais.orientacao == "paisagem"

    # Template da série com anatomia medida
    spec_serie = obter_layout("serie_dinamica_2026")
    assert spec_serie.orientacao == "retrato"

    spec_serie_tip = obter_layout("serie_tipologia")
    assert spec_serie_tip.orientacao == "paisagem"


def test_listar_layouts() -> None:
    layouts = listar_layouts()
    assert len(layouts) >= 2
    ids = [l["id"] for l in layouts]
    assert "harmonia_dinamica_retrato" in ids
    assert "harmonia_tematico_paisagem" in ids


def test_medir_pdf_referencia() -> None:
    pdf_ref = _RAIZ / "Referencias_IMAP" / "Mapas" / "01" / "Dinamica_2026_quantitativos.pdf"
    if not pdf_ref.is_file():
        pytest.skip("PDF de referência não encontrado")

    spec = medir(pdf_ref, id="medido_dinamica_2026", nome="Dinâmica 2026 Medida")
    assert isinstance(spec, LayoutSpec)
    assert spec.orientacao == "retrato"
    assert "mapa" in spec.elementos
    assert spec.elementos["mapa"].x0 > 0
    assert spec.elementos["mapa"].x1 > 180
    assert "titulo" in spec.elementos
    assert spec.elementos["titulo"].y0 > 5
