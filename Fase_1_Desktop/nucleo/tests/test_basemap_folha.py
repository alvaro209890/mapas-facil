"""W9-06 — resolução do recorte do basemap por folha e o aviso S17.

O GetMap é pedido com pixels proporcionais ao quadro no papel: A4 em 300 dpi são ~2.320 px; A0
para no teto de 9.000 px (≈226 dpi). Quando o mosaico não tem resolução para a folha, o check
`S17` avisa em vez de reamostrar 4× e entregar uma imagem borrada e pesada.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.motores import basemap, folhas as folhas_mod, perfil_pagina

ESPERADO = {
    # formato: (largura_px, dpi efetivo) medidos do plano W-09 §Raster
    "A4": (2321, 300.0),
    "A3": (3282, 300.0),
    "A2": (4642, 300.0),
    "A1": (5449, 249.0),
    "A0": (7002, 226.0),
}


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
def test_largura_do_getmap_por_folha(formato: str) -> None:
    perfil = perfil_pagina.perfil_para(folhas_mod.folha_padrao(formato, "retrato"))
    largura = basemap.largura_para_folha(perfil)
    esperado_px, esperado_dpi = ESPERADO[formato]
    assert largura == pytest.approx(esperado_px, abs=2)
    dpi = basemap.dpi_efetivo(largura, perfil.mapa.largura)
    assert dpi == pytest.approx(esperado_dpi, abs=1.5)


def test_sem_perfil_usa_o_padrao_conservador() -> None:
    assert basemap.largura_para_folha(None) == basemap.LARGURA_PADRAO


@pytest.mark.parametrize(
    "largura_px,quadro_mm,esperado_aviso",
    [
        (2321, 196.5, False),  # A4 a 300 dpi
        (7002, 786.9, False),  # A0 no teto, 226 dpi > 220
        (1600, 196.5, True),  # padrão antigo em A4: 207 dpi, avisa
        (3210, 786.9, True),  # A0 com pixels de A4: 104 dpi, avisa
    ],
)
def test_aviso_s17(largura_px: int, quadro_mm: float, esperado_aviso: bool) -> None:
    avaliacao = basemap.avaliar_resolucao(largura_px, (quadro_mm, quadro_mm))
    assert avaliacao["aviso_resolucao"] is esperado_aviso
    assert avaliacao["dpi_efetivo"] == pytest.approx(largura_px / (quadro_mm / 25.4), abs=0.1)


def test_sem_quadro_nao_mede_dpi() -> None:
    avaliacao = basemap.avaliar_resolucao(2321, None)
    assert avaliacao == {"dpi_efetivo": None, "aviso_resolucao": False}


def test_teto_de_pixels_respeitado_em_toda_folha() -> None:
    for formato in folhas_mod.ORDEM:
        perfil = perfil_pagina.perfil_para(folhas_mod.folha_padrao(formato, "retrato"))
        largura = basemap.largura_para_folha(perfil)
        altura = int(largura * perfil.mapa.altura / perfil.mapa.largura)
        teto = perfil_pagina.TETO_PX_LADO_MAIOR.get(formato)
        if teto:
            assert max(largura, altura) <= teto + 2, f"{formato}: {max(largura, altura)} px"
