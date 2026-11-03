"""W9-01 — perfil de página derivado por folha (D31).

A regra é uma só: **A4 é medido, o resto é o A4 vezes `k`**. Nada é remedido em A3–A0 e
nenhum número novo é inventado; o teste prova as duas metades — a A4 volta intocada e as
outras folhas são exatamente `k` vezes ela, dentro do papel.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.motores import folhas as folhas_mod
from mapasfacil_nucleo.motores import perfil_pagina as pp

CAIXAS = ("mapa", "titulo", "rosa", "minimapa", "metadados", "legenda", "logo", "tabela")
FONTES = ("pt_titulo", "pt_metadados", "pt_legenda", "pt_grade", "pt_legenda_titulo")


def folha(formato: str, orientacao: str = "retrato") -> dict:
    return folhas_mod.folha_padrao(formato, orientacao)


@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
def test_a4_devolve_o_perfil_medido_sem_tocar_em_nada(orientacao: str) -> None:
    medido = pp.obter(orientacao)
    derivado = pp.perfil_para(folha("A4", orientacao))
    assert derivado is medido, "A4 tem de ser o próprio objeto medido, não uma cópia"
    assert derivado.fator == 1.0
    for nome in CAIXAS:
        assert getattr(derivado, nome) == getattr(medido, nome)


def test_sem_folha_cai_na_a4_retrato() -> None:
    assert pp.perfil_para(None) is pp.RETRATO
    assert pp.perfil_para({}) is pp.RETRATO


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
def test_pagina_exata_da_folha(formato: str, orientacao: str) -> None:
    perfil = pp.perfil_para(folha(formato, orientacao))
    largura, altura = folhas_mod.folha_mm(formato, orientacao)
    assert (perfil.largura_mm, perfil.altura_mm) == (largura, altura)
    assert perfil.orientacao == orientacao
    # figsize do matplotlib tem de bater com o papel (senão o PDF sai em outro tamanho)
    assert perfil.figsize_pol[0] == pytest.approx(largura / 25.4, abs=1e-9)
    assert perfil.figsize_pol[1] == pytest.approx(altura / 25.4, abs=1e-9)


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
def test_toda_caixa_e_a_a4_vezes_k(formato: str, orientacao: str) -> None:
    base = pp.obter(orientacao)
    perfil = pp.perfil_para(folha(formato, orientacao))
    k = folhas_mod.fator_k(formato)
    assert perfil.fator == pytest.approx(k, rel=1e-12)

    def esperado(valor: float, pagina_base: float, pagina: float) -> float:
        # borda continua borda: as folhas ISO não têm razão exatamente √2, então a
        # caixa que encosta no papel é encaixada na página (ver `_escalar_com_borda`)
        if abs(valor) < 1e-9:
            return 0.0
        if abs(valor - pagina_base) < 1e-9:
            return pagina
        return valor * k

    for nome in CAIXAS:
        b = getattr(base, nome)
        d = getattr(perfil, nome)
        assert d.x0 == pytest.approx(esperado(b.x0, base.largura_mm, perfil.largura_mm), abs=1e-9), nome
        assert d.y0 == pytest.approx(esperado(b.y0, base.altura_mm, perfil.altura_mm), abs=1e-9), nome
        assert d.x1 == pytest.approx(esperado(b.x1, base.largura_mm, perfil.largura_mm), abs=1e-9), nome
        assert d.y1 == pytest.approx(esperado(b.y1, base.altura_mm, perfil.altura_mm), abs=1e-9), nome
        # proporcional preserva a forma — mas só se nenhuma coordenada foi encaixada na
        # borda. Quem encosta no papel absorve a diferença de arredondamento do ISO
        # (A1 tem 841 mm de altura onde k · A4 daria 840,1), que é justamente o que o
        # encaixe existe para corrigir.
        encostada = any(
            abs(v) < 1e-9 or abs(v - pag) < 1e-9
            for v, pag in (
                (b.x0, base.largura_mm), (b.x1, base.largura_mm),
                (b.y0, base.altura_mm), (b.y1, base.altura_mm),
            )
        )
        if not encostada:
            assert d.largura / d.altura == pytest.approx(b.largura / b.altura, rel=1e-9), nome


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
def test_fontes_escalam_junto(formato: str, orientacao: str) -> None:
    base = pp.obter(orientacao)
    perfil = pp.perfil_para(folha(formato, orientacao))
    k = folhas_mod.fator_k(formato)
    for nome in FONTES:
        assert getattr(perfil, nome) == pytest.approx(getattr(base, nome) * k, abs=1e-9), nome
    assert perfil.escalado(1.0) == pytest.approx(k, abs=1e-12)


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
def test_nenhuma_caixa_sai_do_papel(formato: str, orientacao: str) -> None:
    """Escalar não pode empurrar caixa para fora da página — é o erro clássico do D31."""
    perfil = pp.perfil_para(folha(formato, orientacao))
    for nome in CAIXAS:
        c = getattr(perfil, nome)
        assert c.x0 >= -1e-6 and c.y0 >= -1e-6, f"{nome} começa fora da página"
        assert c.x1 <= perfil.largura_mm + 1e-6, f"{nome} passa da largura"
        assert c.y1 <= perfil.altura_mm + 1e-6, f"{nome} passa da altura"
        assert c.largura > 0 and c.altura > 0, f"{nome} degenerada"


def test_a0_e_o_a4_vezes_quatro_em_todas_as_caixas_e_pt() -> None:
    """O caso do plano: A0 = A4 × 4 (k = 841/210 ≈ 4,0048) em toda caixa e todo pt."""
    a4, a0 = pp.RETRATO, pp.perfil_para(folha("A0", "retrato"))
    k = 841.0 / 210.0
    assert a0.fator == pytest.approx(k, abs=1e-12)
    assert a0.mapa.largura == pytest.approx(a4.mapa.largura * k, abs=1e-9)
    assert a0.mapa.altura == pytest.approx(a4.mapa.altura * k, abs=1e-9)
    assert a0.pt_metadados == pytest.approx(a4.pt_metadados * k, abs=1e-9)
    assert a0.pt_titulo == pytest.approx(a4.pt_titulo * k, abs=1e-9)
    assert a0.largura_mm == 841.0 and a0.altura_mm == 1189.0


@pytest.mark.parametrize("formato", folhas_mod.ORDEM[1:])
def test_id_da_folha_derivada_diz_o_formato(formato: str) -> None:
    perfil = pp.perfil_para(folha(formato, "paisagem"))
    assert perfil.id == f"{formato}:paisagem"


def test_escala_elementos_legivel_nao_existe_ainda() -> None:
    with pytest.raises(ErroNucleo) as exc:
        pp.perfil_para({"formato": "A3", "orientacao": "retrato", "escala_elementos": "legivel"})
    assert exc.value.codigo == "NU-303"


def test_formato_invalido_levanta_erro_de_folha() -> None:
    with pytest.raises(ErroNucleo) as exc:
        pp.perfil_para({"formato": "A7", "orientacao": "retrato"})
    assert exc.value.codigo == "NU-301"


# --- W9-02: dpi do raster por folha (W-09 §Raster) ---------------------------------


def test_a4_mantem_300_dpi_do_gabarito() -> None:
    for orientacao in folhas_mod.ORIENTACOES:
        assert pp.perfil_para(folha("A4", orientacao)).dpi_raster() == 300


@pytest.mark.parametrize(
    "formato,minimo,maximo",
    [("A3", 300, 300), ("A2", 300, 300), ("A1", 240, 260), ("A0", 220, 235)],
)
def test_dpi_por_folha_respeita_o_teto_de_pixels(formato: str, minimo: int, maximo: int) -> None:
    perfil = pp.perfil_para(folha(formato, "retrato"))
    dpi = perfil.dpi_raster()
    assert minimo <= dpi <= maximo, f"{formato}: {dpi} dpi fora da faixa do plano"
    lado_px = max(perfil.mapa.largura, perfil.mapa.altura) / 25.4 * dpi
    teto = pp.TETO_PX_LADO_MAIOR.get(formato)
    if teto:
        assert lado_px <= teto + 1, f"{formato}: {lado_px:.0f} px passa do teto {teto}"


def test_dpi_nunca_desce_abaixo_do_minimo_utilizavel() -> None:
    """Mesmo numa folha absurda, não devolve 0 nem dpi de fax."""
    gigante = pp.perfil_para(folha("A0", "retrato"))
    assert gigante.dpi_raster(alvo=10) >= 72


# --- escalar_perfil: perfil MEDIDO de um modelo da série ---------------------------


def test_escalar_perfil_preserva_o_modelo_medido_e_a_orientacao() -> None:
    medido = pp.PerfilPagina(
        id="retrato:tipologia",
        orientacao="paisagem",
        largura_mm=297.0,
        altura_mm=210.0,
        mapa=pp.Caixa(5.6, 4.8, 291.1, 151.0),
        titulo=pp.Caixa(107.2, 3.0, 185.0, 20.5),
        rosa=pp.Caixa(276.7, 4.3, 288.5, 21.7),
        minimapa=pp.Caixa(2.0, 172.0, 62.0, 208.0),
        metadados=pp.Caixa(76.4, 173.8, 156.2, 205.3),
        legenda=pp.Caixa(177.1, 172.0, 227.0, 208.2),
        logo=pp.Caixa(245.0, 175.0, 292.0, 205.0),
        tabela=pp.Caixa(80.0, 140.0, 285.0, 160.0),
        crs_padrao="EPSG:31982",
        titulo_legenda="LEGENDA",
        pt_titulo=26.0,
        pt_metadados=11.0,
        pt_legenda=10.0,
        pt_grade=6.0,
    )
    # A4: a série devolve o próprio medido, mesmo que a `folha` diga retrato
    assert pp.escalar_perfil(medido, folha("A4", "retrato")) is medido

    a2 = pp.escalar_perfil(medido, folha("A2", "retrato"))
    assert a2.orientacao == "paisagem", "o modelo medido manda na orientação"
    assert (a2.largura_mm, a2.altura_mm) == (594.0, 420.0)
    k = folhas_mod.fator_k("A2")
    assert a2.mapa.x1 == pytest.approx(291.1 * k, abs=1e-9)
    assert a2.pt_metadados == pytest.approx(11.0 * k, abs=1e-9)
    assert a2.formato == "A2"
