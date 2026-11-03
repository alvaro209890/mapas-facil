"""W-10 — enquadramento: faixa útil, margem de 15 %, degraus e escala única da série.

O teste de ouro é o da **Análise PH**: o bloco de 12 matrículas tem 12,1 km de largura e saiu a
1:50.000 em 28,5 cm de quadro. A conta é 12,1 km × 1,15 = 13,9 km em 285,5 mm → 1:48.737 →
arredonda para cima no degrau de 5.000 → **1:50.000**.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.motores import enquadramento as enq

# Bloco da PH: 12,1 km × 6,0 km (a largura é o que manda na folha paisagem).
PH = {"xmin": 600_000.0, "ymin": 8_300_000.0, "xmax": 612_100.0, "ymax": 8_306_000.0}


def test_ph_sai_a_1_50000() -> None:
    perfil = enq.perfil_para("A4", "paisagem")
    resultado = enq.enquadrar(PH, perfil, alternativas=False)
    assert resultado.escala == 50_000
    assert resultado.quadro_mm[0] == pytest.approx(285.5, abs=0.2)


def test_conta_da_ph_antes_do_arredondamento() -> None:
    """A escala contínua tem de dar ~48.700 — se mudar a margem, este número muda."""
    continua = enq.escala_minima(PH, "A4", "paisagem")
    assert 48_000 < continua < 49_500
    assert enq.escala_redonda(continua) == 50_000


@pytest.mark.parametrize(
    ("calculada", "esperada"),
    [
        (2_180, 2_500),
        (10_000, 10_000),
        (10_001, 15_000),
        (48_737, 50_000),
        (103_200, 105_000),
        (200_000, 200_000),
        (200_001, 250_000),
        (812_000, 850_000),
        (1_000_000, 1_000_000),
        (1_000_001, 1_100_000),
        (8_335_900, 8_400_000),
    ],
)
def test_degraus(calculada: float, esperada: int) -> None:
    assert enq.escala_redonda(calculada) == esperada


def test_degrau_por_faixa() -> None:
    assert enq.degrau(9_000) == 500
    assert enq.degrau(10_000) == 500
    assert enq.degrau(10_001) == 5_000
    assert enq.degrau(199_000) == 5_000
    assert enq.degrau(500_000) == 50_000
    assert enq.degrau(2_000_000) == 100_000


def test_margem_padrao_e_15_por_cento() -> None:
    assert enq.MARGEM == pytest.approx(0.15)


# --------------------------------------------------------------- faixa útil
def test_faixa_util_fica_abaixo_do_titulo() -> None:
    perfil = enq.perfil_para("A4", "paisagem")
    faixa = enq.faixa_util(perfil)
    # O título cobre o topo do quadro: a faixa tem de começar embaixo dele.
    assert faixa.y0 >= perfil.titulo.y1 - 0.01
    assert faixa.largura == pytest.approx(perfil.mapa.largura, abs=0.2)
    assert faixa.altura < perfil.mapa.altura


def test_faixa_util_no_retrato() -> None:
    perfil = enq.perfil_para("A4", "retrato")
    faixa = enq.faixa_util(perfil)
    assert faixa.y0 >= perfil.titulo.y1 - 0.01
    assert faixa.x0 >= perfil.mapa.x0 - 0.01


def test_zona_proibida_extra_diminui_a_faixa() -> None:
    perfil = enq.perfil_para("A4", "paisagem")
    sem = enq.faixa_util(perfil)
    tabela = enq.Caixa(80.0, 140.0, 285.0, 160.0)  # tabela do MapSpec caindo sobre o quadro
    com = enq.faixa_util(perfil, [tabela])
    assert com.altura < sem.altura


# ------------------------------------------------------ caixa de conteúdo
def test_caixa_imovel_ignora_alvo() -> None:
    geometrias = [
        {"bbox": {"xmin": 0, "ymin": 0, "xmax": 1000, "ymax": 1000}, "papel": "imovel"},
        {"bbox": {"xmin": 9000, "ymin": 9000, "xmax": 9500, "ymax": 9500}, "papel": "alvo"},
    ]
    assert enq.caixa_de_conteudo(geometrias, "imovel") == (0.0, 0.0, 1000.0, 1000.0)


def test_caixa_imovel_mais_alvo_une() -> None:
    geometrias = [
        {"bbox": {"xmin": 0, "ymin": 0, "xmax": 1000, "ymax": 1000}, "papel": "imovel"},
        {"bbox": {"xmin": 9000, "ymin": 9000, "xmax": 9500, "ymax": 9500}, "papel": "alvo"},
    ]
    assert enq.caixa_de_conteudo(geometrias, "imovel_mais_alvo") == (0.0, 0.0, 9500.0, 9500.0)


def test_caixa_area_tematica_usa_so_o_tema() -> None:
    geometrias = [
        {"bbox": {"xmin": 0, "ymin": 0, "xmax": 1000, "ymax": 1000}, "papel": "imovel"},
        {"bbox": {"xmin": 200, "ymin": 200, "xmax": 400, "ymax": 500}, "papel": "tema"},
    ]
    assert enq.caixa_de_conteudo(geometrias, "area_tematica") == (200.0, 200.0, 400.0, 500.0)


def test_sem_tema_cai_no_imovel() -> None:
    geometrias = [{"bbox": {"xmin": 0, "ymin": 0, "xmax": 1000, "ymax": 1000}, "papel": "imovel"}]
    assert enq.caixa_de_conteudo(geometrias, "area_tematica") == (0.0, 0.0, 1000.0, 1000.0)


def test_tipo_desconhecido() -> None:
    with pytest.raises(ErroNucleo) as exc:
        enq.caixa_de_conteudo(PH, "tudo")
    assert exc.value.codigo == "NU-311"


# --------------------------------------------------------------------- CRS
@pytest.mark.parametrize(
    ("lon", "esperado"),
    # Zona 20: 66–60° W · zona 21: 60–54° W · zona 22: 54–48° W (o MT é cortado pelas três).
    [(-61.0, "31980"), (-60.5, "31980"), (-60.0, "31981"), (-57.0, "31981"), (-54.0, "31982")],
)
def test_crs_por_zona(lon: float, esperado: str) -> None:
    assert enq.crs_utm(lon) == esperado


def test_enquadramento_usa_a_zona_do_centroide() -> None:
    # Querência-MT fica a ~52,5° W: centro em -52,5 => zona 22 (caso real dos laudos da IMAP).
    bbox = {"xmin": -53.0, "ymin": -12.6, "xmax": -52.0, "ymax": -11.6}
    resultado = enq.enquadrar(bbox, enq.perfil_para("A4", "retrato"), alternativas=False)
    assert resultado.crs == "31982"


# ------------------------------------------------------------------ escala
def test_escala_fixa_que_cabe_e_aceita() -> None:
    resultado = enq.enquadrar(
        PH, enq.perfil_para("A3", "paisagem"), escala_fixa=60_000, alternativas=False
    )
    assert resultado.escala == 60_000


def test_escala_fixa_que_nao_cabe_nao_corta_e_explica() -> None:
    with pytest.raises(ErroNucleo) as exc:
        enq.enquadrar(PH, enq.perfil_para("A4", "paisagem"), escala_fixa=25_000, alternativas=False)
    erro = exc.value
    assert erro.codigo == "NU-310"
    assert "corta" in erro.mensagem
    assert "1:50.000" in erro.mensagem
    assert erro.detalhes is not None
    assert erro.detalhes["escala_minima"] == 50_000
    assert erro.detalhes["corte_pct"] > 40


def test_extent_tem_o_tamanho_da_faixa_na_escala() -> None:
    resultado = enq.enquadrar(PH, enq.perfil_para("A4", "paisagem"), alternativas=False)
    largura_m = resultado.extent[2] - resultado.extent[0]
    altura_m = resultado.extent[3] - resultado.extent[1]
    assert largura_m == pytest.approx(resultado.quadro_mm[0] / 1000.0 * resultado.escala, rel=1e-6)
    assert altura_m == pytest.approx(resultado.quadro_mm[1] / 1000.0 * resultado.escala, rel=1e-6)


def test_centro_do_imovel_no_centro_do_extent() -> None:
    resultado = enq.enquadrar(PH, enq.perfil_para("A4", "paisagem"), alternativas=False)
    centro_bbox = ((PH["xmin"] + PH["xmax"]) / 2, (PH["ymin"] + PH["ymax"]) / 2)
    centro_extent = (
        (resultado.extent[0] + resultado.extent[2]) / 2,
        (resultado.extent[1] + resultado.extent[3]) / 2,
    )
    assert centro_extent[0] == pytest.approx(centro_bbox[0], abs=0.01)
    assert centro_extent[1] == pytest.approx(centro_bbox[1], abs=0.01)


def test_deslocamento_aponta_para_a_faixa() -> None:
    resultado = enq.enquadrar(PH, enq.perfil_para("A4", "paisagem"), alternativas=False)
    perfil = enq.perfil_para("A4", "paisagem")
    faixa = enq.faixa_util(perfil)
    esperado = faixa.centro[1] - perfil.mapa.centro[1]
    assert resultado.deslocamento_mm[1] == pytest.approx(esperado, abs=0.05)
    assert resultado.deslocamento_mm[0] == pytest.approx(0.0, abs=0.05)


# --------------------------------------------------------------- série
def test_escala_da_serie_e_a_maior() -> None:
    perfil = enq.perfil_para("A4", "paisagem")
    um = enq.enquadrar(PH, perfil, alternativas=False)
    outro = enq.enquadrar(
        {"xmin": 600_000, "ymin": 8_300_000, "xmax": 603_000, "ymax": 8_302_000},
        perfil,
        alternativas=False,
    )
    assert outro.escala < um.escala
    assert enq.escala_da_serie([um, outro]) == um.escala


def test_imovel_mais_alvo_fica_fora_da_escala_unica() -> None:
    perfil = enq.perfil_para("A4", "paisagem")
    imovel = enq.enquadrar(PH, perfil, alternativas=False)
    contexto = enq.enquadrar(
        {"xmin": 600_000, "ymin": 8_300_000, "xmax": 900_000, "ymax": 8_500_000},
        perfil,
        tipo="imovel_mais_alvo",
        alternativas=False,
    )
    assert contexto.escala > imovel.escala
    assert enq.escala_da_serie([imovel, contexto]) == imovel.escala


def test_com_escala_mantem_o_centro_e_muda_o_extent() -> None:
    perfil = enq.perfil_para("A4", "paisagem")
    resultado = enq.enquadrar(PH, perfil, alternativas=False)
    novo = enq.com_escala(resultado, resultado.escala * 2)
    assert novo.escala == resultado.escala * 2
    assert (novo.extent[0] + novo.extent[2]) / 2 == pytest.approx(
        (resultado.extent[0] + resultado.extent[2]) / 2
    )
    assert novo.extent[2] - novo.extent[0] > resultado.extent[2] - resultado.extent[0]


# ---------------------------------------------------------- tabela e folhas
def test_alternativas_cobrem_folha_x_orientacao() -> None:
    resultado = enq.enquadrar(PH, enq.perfil_para("A4", "paisagem"))
    assert len(resultado.alternativas) == 10
    combinacoes = {(a["folha"], a["orientacao"]) for a in resultado.alternativas}
    assert ("A0", "retrato") in combinacoes
    assert ("A4", "paisagem") in combinacoes


def test_tabela_sugere_folha_maior_para_o_bloco_da_ph() -> None:
    melhor = enq.melhor(PH)
    assert melhor is not None
    assert melhor["folha"] in {"A3", "A2"}
    assert melhor["aproveitamento_pct"] > 60


def test_para_dict_tem_escala_texto_em_pt_br() -> None:
    linha = enq.para_dict(PH, "A4", "paisagem")
    assert linha["escala_texto"] == f"1:{linha['escala']:,}".replace(",", ".")
    assert linha["faixa_util_mm"][0] == pytest.approx(285.5, abs=0.2)


def test_folhas_maiores_dao_escala_mais_detalhada() -> None:
    escalas = [
        enq.enquadrar(PH, enq.perfil_para(formato, "paisagem"), alternativas=False).escala
        for formato in ("A4", "A3", "A2", "A1", "A0")
    ]
    assert escalas == sorted(escalas, reverse=True)
    assert escalas[0] > escalas[-1]


def test_geometria_degenerada() -> None:
    with pytest.raises(ErroNucleo) as exc:
        enq.enquadrar(
            {"xmin": 0, "ymin": 0, "xmax": 0, "ymax": 0},
            enq.perfil_para("A4", "paisagem"),
            alternativas=False,
        )
    assert exc.value.codigo == "NU-311"


# ------------------------------------------------- escala da série (passo 6)
def test_eh_degrau_aceita_o_que_o_arredondamento_produz() -> None:
    from mapasfacil_nucleo.mapspec.validar import escala_valida

    for valor in (50_000, 65_000, 850_000, 2_500, 20_000, 105_000):
        assert enq.eh_degrau(valor) is True
        assert escala_valida(valor) is True


def test_eh_degrau_recusa_fora_da_grade() -> None:
    for valor in (48_737, 103_200, 1, 0, -5_000):
        assert enq.eh_degrau(valor) is False


def test_escala_do_enquadramento_reproduz_ph() -> None:
    """A conta que a série faz por receita: 12,1 km com folga 1,12 na faixa do A4 paisagem."""
    escala = enq.escala_do_enquadramento(PH, "A4", "paisagem", folga=1.12)
    assert escala % 5_000 == 0
    assert 50_000 <= escala <= 60_000


def test_serie_do_bloco_usa_a_mesma_escala() -> None:
    """Mapas do imóvel (mesma folga) e mapa de contexto: só o bloco unifica a escala."""
    perfil = enq.perfil_para("A4", "paisagem")
    bloco = [
        enq.enquadrar(PH, perfil, alternativas=False),
        enq.enquadrar(
            {"xmin": 600_000, "ymin": 8_300_000, "xmax": 609_000, "ymax": 8_305_000},
            perfil,
            alternativas=False,
        ),
    ]
    contexto = enq.enquadrar(
        {"xmin": 600_000, "ymin": 8_300_000, "xmax": 900_000, "ymax": 8_500_000},
        perfil,
        tipo="imovel_mais_alvo",
        alternativas=False,
    )
    unica = enq.escala_da_serie([*bloco, contexto])
    assert unica == max(e.escala for e in bloco)
    reaplicados = [enq.com_escala(e, unica) for e in bloco]
    assert len({e.escala for e in reaplicados}) == 1
