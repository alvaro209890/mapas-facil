"""W9-04 — a grade DMS rende 4 a 8 rótulos por eixo em **qualquer** folha (check S07).

O passo não é escolhido pela folha: é escolhido pelo varrimento em graus do quadro, que já é
`quadro_mm × escala`. Como a `folha` muda o quadro e o enquadramento muda a escala, os dois
caminhos chegam aqui por este teste — a folha grande em escala alta continua legível em vez de
virar uma tarja de segmentos de 5″.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.motores import folhas as folhas_mod
from mapasfacil_nucleo.motores import grade_dms, perfil_pagina

ESCALAS = (5000, 10000, 25000, 50000, 100000, 250000, 500000)

METROS_POR_GRAU = 111_320.0
"""Grau de latitude na latitude do MT; a diferença entre 9° e 13° S é <0,3%."""


def _span_graus(formato: str, orientacao: str, escala: int) -> tuple[float, float]:
    perfil = perfil_pagina.perfil_para(folhas_mod.folha_padrao(formato, orientacao))
    span_x = perfil.mapa.largura / 1000.0 * escala / METROS_POR_GRAU
    span_y = perfil.mapa.altura / 1000.0 * escala / METROS_POR_GRAU
    return span_x, span_y


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
@pytest.mark.parametrize("escala", ESCALAS)
def test_quatro_a_oito_rotulos_por_eixo(formato: str, orientacao: str, escala: int) -> None:
    span_x, span_y = _span_graus(formato, orientacao, escala)
    for eixo, span in (("x", span_x), ("y", span_y)):
        passo = grade_dms.escolher_passo(span)
        n = span * 3600.0 / passo
        assert grade_dms.ALVO_MIN <= n <= grade_dms.ALVO_MAX, (
            f"{formato} {orientacao} 1:{escala} eixo {eixo}: {n:.2f} rótulos com passo {passo}s"
        )


def test_extensao_minuscula_ainda_ganha_uma_linha_de_grade() -> None:
    """Imóvel pequeno em 1:2.000 (7,2″ de arco) não pode cair no passo de 1° — sem grade.

    Com 4–8 rótulos impossível, a regra de baixo é "pelo menos uma linha": o passo tem de
    caber dentro do quadro.
    """
    span_seg = 0.002 * 3600.0  # 7,2″
    passo = grade_dms.escolher_passo(0.002)
    assert passo <= span_seg, f"passo {passo}s não cabe em {span_seg:.1f}s de quadro"
    assert passo < 3600, "voltou ao passo de 1° (nenhuma linha cruzaria o mapa)"
    assert len(grade_dms.valores_ticks(-52.0, -52.0 + 0.002, passo)) >= 1


def test_folha_maior_pede_passo_mais_grosso_no_mesmo_imovel() -> None:
    """A4 → A0 com a mesma escala: mais área no papel ⇒ passo de grau maior."""
    a4, a0 = _span_graus("A4", "retrato", 25000)[0], _span_graus("A0", "retrato", 25000)[0]
    assert a0 > a4
    assert grade_dms.escolher_passo(a0) >= grade_dms.escolher_passo(a4)
