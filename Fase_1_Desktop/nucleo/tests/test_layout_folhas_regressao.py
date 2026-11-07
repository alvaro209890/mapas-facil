"""Testes de regressão: ciclo 1 pós revisão reprovada.

1. Idempotência e escala única de LayoutSpec/PerfilPagina para A4..A0 retrato e paisagem;
2. layout.medir metadados pdf_origem apenas basename sem caminho absoluto;
3. mapspec.validar falhar fechado com erro compreensível ao injetar exception;
4. loader.obter_layout honrar MANIFEST layout_ref para os 26 templates com detecção de ciclos.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.layout import (
    LayoutSpec,
    carregar,
    de_perfil,
    medir,
    obter_layout,
    perfil_do_layout,
    validar,
)
from mapasfacil_nucleo.mapspec.validar import validar as validar_mapspec
from mapasfacil_nucleo.motores import folhas as folhas_mod
from mapasfacil_nucleo.motores.manifesto import carregar as carregar_manifesto
from mapasfacil_nucleo.motores.nativo import _perfil_do_mapspec, gerar_pdf_minimo
from mapasfacil_nucleo.motores.perfil_pagina import (
    PAISAGEM,
    RETRATO,
    caixas_fora_da_pagina,
)
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm

_RAIZ = raiz_repositorio()


# ---------------------------------------------------------------------------
# (1) Teste _perfil_do_mapspec caixas_fora_da_pagina para A4..A0 em retrato e paisagem
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formato", ["A4", "A3", "A2", "A1", "A0"])
@pytest.mark.parametrize("orientacao", ["retrato", "paisagem"])
def test_perfil_do_mapspec_sem_caixas_fora_da_pagina_a4_a0(formato: str, orientacao: str) -> None:
    template = "dinamica_retrato" if orientacao == "retrato" else "tipologia_paisagem"
    mapspec = {
        "template": template,
        "folha": {"formato": formato, "orientacao": orientacao},
        "elementos_layout": {"minimapa": True},
        "imovel": {"municipio": {"nome": "Cuiabá"}},
    }
    perfil = _perfil_do_mapspec(mapspec)

    largura_esp, altura_esp = folhas_mod.folha_mm(formato, orientacao)
    assert abs(perfil.largura_mm - largura_esp) <= 0.5
    assert abs(perfil.altura_mm - altura_esp) <= 0.5
    assert perfil.fator == pytest.approx(folhas_mod.fator_k(formato), rel=1e-5)

    fora = caixas_fora_da_pagina(perfil, tolerancia_mm=0.5)
    assert not fora, f"Caixas vazaram em {formato} {orientacao}: {fora}"
    assert perfil.mapa.x1 <= perfil.largura_mm + 0.5
    assert perfil.mapa.y1 <= perfil.altura_mm + 0.5


def test_perfil_do_layout_idempotente_com_layout_ja_escalado() -> None:
    """Um LayoutSpec já escalado para A3 não deve ser re-escalado ao passar folha A3."""
    spec_a4 = de_perfil(RETRATO)
    perfil_a3_primeiro = perfil_do_layout(spec_a4, folha={"formato": "A3", "orientacao": "retrato"})
    spec_a3 = de_perfil(perfil_a3_primeiro)

    # spec_a3 já tem dimensões A3 (297x420)
    assert spec_a3.dimensoes_mm.largura == 297.0
    assert spec_a3.dimensoes_mm.altura == 420.0

    # Conversão passando folha A3 novamente: deve ser idempotente
    perfil_a3_segundo = perfil_do_layout(spec_a3, folha={"formato": "A3", "orientacao": "retrato"})
    assert perfil_a3_segundo.largura_mm == 297.0
    assert perfil_a3_segundo.altura_mm == 420.0
    assert perfil_a3_segundo.mapa.x1 == pytest.approx(perfil_a3_primeiro.mapa.x1, abs=0.1)
    assert perfil_a3_segundo.pt_titulo == pytest.approx(perfil_a3_primeiro.pt_titulo, abs=0.1)
    assert perfil_a3_segundo.fator == pytest.approx(perfil_a3_primeiro.fator, rel=1e-5)

    fora = caixas_fora_da_pagina(perfil_a3_segundo, tolerancia_mm=0.5)
    assert not fora, f"Caixas vazaram na re-conversão idempotente: {fora}"


def test_render_real_a3_paisagem_minimapa(tmp_path: Path) -> None:
    """Render REAL de A3 paisagem com minimapa ativado (não pode dar crash de altura negativa)."""
    pasta_shp = tmp_path / "SHP"
    pasta_shp.mkdir()
    atp = pasta_shp / "ATP.shp"
    escrever_shapefile_quadrado_utm(atp, nome="ATP_teste", lado_m=3000)

    guard = WorkspaceGuard(tmp_path)
    mapspec = {
        "titulo": "Teste A3 Paisagem Minimapa Real",
        "template": "tipologia_paisagem",
        "folha": {"formato": "A3", "orientacao": "paisagem"},
        "imovel": {
            "nome": "Fazenda Modelo",
            "geometria": "local.ATP",
            "municipio": {"nome": "Cuiabá"},
        },
        "camadas": [
            {"id": "ATP", "fonte": "local.ATP", "estilo": "perimetro_imovel", "ordem": 10}
        ],
        "elementos_layout": {"minimapa": True},
        "saidas": ["pdf"],
    }
    pdf_path, artefatos = gerar_pdf_minimo(
        mapspec,
        guard=guard,
        fontes_idx={"ATP": "SHP/ATP.shp"},
    )
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 0
    assert "layout_spec" in artefatos
    assert artefatos["layout_spec"]["dimensoes_mm"]["largura"] == 420.0
    assert artefatos["layout_spec"]["dimensoes_mm"]["altura"] == 297.0


# ---------------------------------------------------------------------------
# (2) layout.medir metadados pdf_origem apenas basename sem caminhos absolutos
# ---------------------------------------------------------------------------

def test_medir_pdf_origem_apenas_basename() -> None:
    pdf_ref = _RAIZ / "Referencias_IMAP" / "Mapas" / "01" / "Dinamica_2026_quantitativos.pdf"
    if not pdf_ref.is_file():
        pytest.skip("PDF de referência não encontrado")

    spec = medir(pdf_ref, id="medido_teste")
    origem = spec.metadados_medidos.get("pdf_origem")
    assert origem == "Dinamica_2026_quantitativos.pdf"
    assert "/" not in origem
    assert "\\" not in origem
    assert ":" not in origem


# ---------------------------------------------------------------------------
# (3) mapspec validar_regras falhar fechado com erro compreensível ao injetar exception
# ---------------------------------------------------------------------------

def test_mapspec_validar_regras_falha_fechado_exception_injetada() -> None:
    from mapasfacil_nucleo.mapspec.validar import validar_regras

    mapspec = {
        "titulo": "Teste Exception Injetada",
        "template": "dinamica_retrato",
        "layout_spec": {
            "contract_version": 1,
            "versao": 1,
            "id": "qualquer",
            "elementos": {},
        },
    }

    with patch("mapasfacil_nucleo.layout.validar", side_effect=RuntimeError("Falha proposital de teste")):
        erros = validar_regras(mapspec)

    assert any(e["codigo"] == "NU-234" for e in erros), f"Esperava erro NU-234, obteve: {erros}"
    erro_layout = next(e for e in erros if e["codigo"] == "NU-234")
    assert "Falha proposital de teste" in erro_layout["mensagem"] or "Falha ao validar layout_spec" in erro_layout["mensagem"]


# ---------------------------------------------------------------------------
# (4) loader obter_layout honrar MANIFEST layout_ref para 26 templates e detectar ciclos
# ---------------------------------------------------------------------------

def test_loader_obter_layout_honra_manifest_26_templates() -> None:
    manifesto = carregar_manifesto()
    templates = manifesto.get("templates", [])
    assert len(templates) == 26

    for tpl in templates:
        tid = tpl["id"]
        lref = tpl.get("layout_ref")
        assert lref, f"Template {tid} sem layout_ref"

        spec = obter_layout(tid)
        assert isinstance(spec, LayoutSpec), f"Falha ao obter LayoutSpec para {tid}"
        res = validar(spec)
        assert res["valido"] is True, f"Template {tid} gerou spec inválido: {res['erros']}"


def test_loader_obter_layout_detecta_ciclos() -> None:
    """Se houver ciclo na resolução de templates, deve levantar erro claro."""
    with patch.dict(
        "mapasfacil_nucleo.layout.loader._MAPA_TEMPLATES_CONHECIDOS",
        {"ciclo_a": "ciclo_b", "ciclo_b": "ciclo_a"},
        clear=False,
    ):
        with pytest.raises(ValueError, match="[Cc]iclo"):
            obter_layout("ciclo_a")
