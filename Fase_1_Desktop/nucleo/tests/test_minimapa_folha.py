"""W9-05 — minimapa por folha: caixa, espessuras e retângulo localizador (D31 / S01).

O quadradinho que marca o imóvel no minimapa é relativo à caixa: em A0 ele tem de crescer junto,
senão vira um ponto invisível no meio de um mapa de 800 mm.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.motores import folhas as folhas_mod
from mapasfacil_nucleo.motores import minimapa, perfil_pagina


def test_layout_a4_e_o_medido() -> None:
    layout = minimapa.layout_de_perfil(perfil_pagina.RETRATO)
    padrao = minimapa.MiniMapaLayout()
    assert layout.lado_retangulo_mm == pytest.approx(3.5)
    assert (layout.minimapa.x0, layout.minimapa.y1) == (padrao.minimapa.x0, padrao.minimapa.y1)
    assert layout.altura_pagina_mm == pytest.approx(297.0)


@pytest.mark.parametrize("formato", folhas_mod.ORDEM[1:])
def test_layout_da_folha_e_a_a4_vezes_k(formato: str) -> None:
    perfil = perfil_pagina.perfil_para(folhas_mod.folha_padrao(formato, "retrato"))
    k = folhas_mod.fator_k(formato)
    layout = minimapa.layout_de_perfil(perfil)
    assert layout.lado_retangulo_mm == pytest.approx(3.5 * k, rel=1e-9)
    assert layout.altura_pagina_mm == pytest.approx(perfil.altura_mm)
    assert layout.minimapa.x1 == pytest.approx(perfil.minimapa.x1, abs=1e-9)
    assert layout.mapa.y1 == pytest.approx(perfil.mapa.y1, abs=1e-9)


def test_sem_perfil_cai_no_padrao_medido() -> None:
    layout = minimapa.layout_de_perfil(object())
    assert layout == minimapa.MiniMapaLayout()


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
def test_retangulo_fica_centrado_no_centroid_em_qualquer_folha(formato: str) -> None:
    """S01: centro do retângulo = centroid do imóvel, em todas as folhas."""
    perfil = perfil_pagina.perfil_para(folhas_mod.folha_padrao(formato, "retrato"))
    layout = minimapa.layout_de_perfil(perfil)
    centro_pagina = (layout.minimapa.x1 - layout.minimapa.x0) / 2 + layout.minimapa.x0, (
        layout.minimapa.y1 - layout.minimapa.y0
    ) / 2 + layout.minimapa.y0
    resultado = minimapa.retangulo_e_guia_L(
        centro_page_mm=centro_pagina, layout=layout
    )
    ret = resultado["retangulo_mm"]
    cx = (ret["x0"] + ret["x1"]) / 2
    cy = (ret["y0"] + ret["y1"]) / 2
    assert cx == pytest.approx(centro_pagina[0], abs=0.01)
    assert cy == pytest.approx(centro_pagina[1], abs=0.01)
    assert ret["x1"] - ret["x0"] == pytest.approx(layout.lado_retangulo_mm, abs=1e-6)
