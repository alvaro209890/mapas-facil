"""W9-03 — espessuras, fontes e halos de `blocos` acompanham a folha (D31).

A regra é uma só, a mesma do perfil: **A4 é o gabarito medido, o resto é o A4
vezes `k`**. Antes desta tarefa a moldura, a grade, os swatches da legenda e o halo
do rótulo eram pt literais: corretos em A4 e finos como cabelo num A0 de 841 mm.

O teste prova as duas metades desenhando a mesma cena em A4 e na folha pedida e
lendo as espessuras de volta dos próprios artistas do matplotlib:

* em A4 cada espessura é o pt literal de hoje (o gabarito não muda);
* em A0/A3 cada espessura — e cada fonte e cada halo — é exatamente `k` vezes a de A4;
* a quebra de linha é folha-invariante, porque caixa e tamanho de fonte escalam juntos.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
import shapefile  # noqa: E402

from mapasfacil_nucleo.motores import blocos  # noqa: E402
from mapasfacil_nucleo.motores import folhas as folhas_mod  # noqa: E402
from mapasfacil_nucleo.motores import perfil_pagina  # noqa: E402

K_A0 = 841.0 / 210.0
"""Fator da A0 em relação à A4 retrato: 841 mm / 210 mm ≈ 4,0048."""

BASE_PT = [0.25, 0.4, 0.5, 0.8, 0.9, 1.0, 1.2, 1.4, 2.2]
"""Os pt literais que a W9-03 passou a escalar. A cena abaixo exercita todos —
se um desaparecer do desenho, o teste de A4 falha e avisa que a cobertura caiu.

O 2,2 é o traço do imóvel na amostra da legenda: desde 04/11/2026 a amostra usa a
espessura da camada no mapa (era 1,6 fixo para todas), como o ArcMap desenha."""


def _perfil(formato: str, orientacao: str = "retrato") -> perfil_pagina.PerfilPagina:
    return perfil_pagina.perfil_para(folhas_mod.folha_padrao(formato, orientacao))


# --------------------------------------------------------------------------- #
# Fixtures de geometria (municípios/UF sintéticos, só para acender o minimapa)
# --------------------------------------------------------------------------- #


def _quadrado(w: shapefile.Writer, x0: float, y0: float, lado: float) -> None:
    w.poly([[[x0, y0], [x0 + lado, y0], [x0 + lado, y0 + lado], [x0, y0 + lado], [x0, y0]]])


def _shp_municipios(caminho) -> "object":
    caminho.parent.mkdir(parents=True, exist_ok=True)
    w = shapefile.Writer(str(caminho), shapeType=shapefile.POLYGON)
    w.field("nome", "C", 80)
    w.field("sigla_uf", "C", 2)
    _quadrado(w, -52.00, -10.00, 0.10)
    w.record("Vila Rica", "MT")
    _quadrado(w, -51.90, -10.00, 0.10)  # vizinho colado, entra na vista do inset
    w.record("Confresa", "MT")
    w.close()
    return caminho


def _shp_ufs(caminho) -> "object":
    caminho.parent.mkdir(parents=True, exist_ok=True)
    w = shapefile.Writer(str(caminho), shapeType=shapefile.POLYGON)
    w.field("sigla_uf", "C", 2)
    _quadrado(w, -53.0, -11.0, 2.0)
    w.record("MT")
    w.close()
    return caminho


# --------------------------------------------------------------------------- #
# Cena e leitura das espessuras de volta dos artistas
# --------------------------------------------------------------------------- #

_GRADE = {
    "x": [{"inferior": 0.25, "superior": 0.75, "rotulo": "52°00'"}],
    "y": [{"esquerda": 0.25, "direita": 0.75, "rotulo": "12°00'"}],
}
_PARES = [
    {"rotulo": "Imóvel", "valor": "Fazenda Harmonia"},
    {"rotulo": "Município", "valor": "Vila Rica/MT"},
]
_ITENS = [
    {"rotulo": "Perímetro do imóvel", "estilo": "perimetro_imovel"},
    {"rotulo": "Área de vegetação nativa", "estilo": "avn"},
]

TEXTO_LONGO = "Área de Preservação Permanente do imóvel rural e entorno imediato"
"""Longo o bastante para transbordar a caixa de título e realmente quebrar."""


def _desenhar_cena(perfil: perfil_pagina.PerfilPagina, pasta) -> plt.Figure:
    """Mesma cena em qualquer folha: todas as funções de `blocos` que traçam linha."""
    fig = plt.figure(figsize=perfil.figsize_pol)
    ax = fig.add_axes(perfil.fracao(perfil.mapa), zorder=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    blocos.moldura_e_grade(ax, perfil, _GRADE, com_linhas=True)
    blocos.caixa_titulo(fig, perfil, "Mapa de teste da anatomia")
    blocos.rosa_dos_ventos(fig, perfil)
    blocos.bloco_metadados(fig, perfil, _PARES)
    blocos.bloco_legenda(fig, perfil, _ITENS)
    blocos.bloco_minimapa(
        fig,
        perfil,
        municipio="Vila Rica",
        uf="MT",
        centroide_lonlat=(-51.95, -9.95),
        shp_municipios=_shp_municipios(pasta / "municipios.shp"),
        shp_ufs=_shp_ufs(pasta / "ufs.shp"),
    )
    blocos.rotulo_imovel(ax, (0.5, 0.5), "Fazenda Harmonia", perfil=perfil)
    return fig


def _largura_halo(efeito) -> float:
    """A espessura que o `withStroke` guarda (é o kwarg do gc, não um método)."""
    return efeito._gc["linewidth"]


def _coletar(fig: plt.Figure) -> tuple[list[float], list[float], list[float]]:
    """`(larguras, fontes, halos)` de todos os artistas, já ordenados."""
    larguras: list[float] = []
    fontes: list[float] = []
    halos: list[float] = []
    for ax in fig.axes:
        if ax.axison:  # eixos "ligados": são os que realmente têm moldura
            for lado in ax.spines.values():
                if lado.get_visible():
                    larguras.append(lado.get_linewidth())
        for linha in ax.lines:
            larguras.append(linha.get_linewidth())
        for patch in ax.patches:
            larguras.append(patch.get_linewidth())
        for texto in ax.texts:
            fontes.append(texto.get_fontsize())
            for efeito in texto.get_path_effects():
                if getattr(efeito, "_gc", None) and "linewidth" in efeito._gc:
                    halos.append(efeito._gc["linewidth"])
    return sorted(larguras), sorted(fontes), sorted(halos)


# --------------------------------------------------------------------------- #
# (a) A4 bit a bit como hoje
# --------------------------------------------------------------------------- #


def test_a4_mantem_as_espessuras_literais_de_hoje(tmp_path) -> None:
    a4 = _perfil("A4")
    assert a4.fator == 1.0
    fig = _desenhar_cena(a4, tmp_path)
    larguras, _, _ = _coletar(fig)
    plt.close(fig)

    presentes = [round(w, 9) for w in sorted(set(larguras))]
    assert presentes == BASE_PT, f"A4 devia usar exatamente {BASE_PT}, achou {presentes}"
    for valor in BASE_PT:
        assert a4.escalado(valor) == valor, "em A4 o escalado tem de ser a identidade"


# --------------------------------------------------------------------------- #
# (b) A0 e (d) A3-paisagem: cada espessura, fonte e halo = A4 × k
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("formato", "orientacao", "k"),
    [("A0", "retrato", K_A0), ("A3", "paisagem", 297.0 / 210.0)],
)
def test_espessuras_fontes_e_halos_sao_a4_vezes_k(formato, orientacao, k, tmp_path) -> None:
    a4 = _perfil("A4", orientacao)
    folha = _perfil(formato, orientacao)
    assert folha.fator == pytest.approx(folhas_mod.fator_k(formato), rel=1e-12)
    assert k == pytest.approx(folhas_mod.fator_k(formato), rel=1e-12)

    fig4 = _desenhar_cena(a4, tmp_path / "a4")
    figf = _desenhar_cena(folha, tmp_path / "folha")
    l4, f4, hal4 = _coletar(fig4)
    lf, ff, half = _coletar(figf)
    plt.close(fig4)
    plt.close(figf)

    for nome, base, escala in (("larguras", l4, lf), ("fontes", f4, ff), ("halos", hal4, half)):
        assert len(base) == len(escala), f"{nome}: cena com nº de artistas diferente"
        assert base, f"{nome}: cena vazia — o teste não provou nada"
        for v4, vf in zip(base, escala):
            assert vf == pytest.approx(v4 * k, rel=1e-9, abs=1e-9), (
                f"{nome}: {vf} não é {v4} × {k}"
            )


def test_halos_escalam_com_a_folha() -> None:
    a4 = _perfil("A4")
    a0 = _perfil("A0")
    assert _largura_halo(blocos.halos(a4, claro=False)[0]) == blocos.LARGURA_HALO_PT
    assert _largura_halo(blocos.halos(a4, claro=True)[0]) == blocos.LARGURA_HALO_PT
    assert _largura_halo(blocos.halos(a0, claro=True)[0]) == pytest.approx(
        blocos.LARGURA_HALO_PT * K_A0, rel=1e-12
    )
    # Sem perfil: valor de A4, sem escala e sem explodir (compatibilidade).
    assert _largura_halo(blocos.halos(None, claro=False)[0]) == blocos.LARGURA_HALO_PT


def test_constantes_de_halo_antigas_nao_sobrevivem() -> None:
    """W9-03: as constantes de módulo viraram função — nenhum caminho pode usá-las."""
    assert not hasattr(blocos, "HALO_ESCURO")
    assert not hasattr(blocos, "HALO_CLARO")


# --------------------------------------------------------------------------- #
# (e) quebra de linha respeita a largura útil escalada
# --------------------------------------------------------------------------- #


def test_quebra_de_linha_e_invariante_entre_a4_e_a0() -> None:
    a4 = _perfil("A4")
    a0 = _perfil("A0")
    # a largura útil da caixa cresce exatamente com a folha...
    assert a0.titulo.largura * 1.6 == pytest.approx(a4.titulo.largura * 1.6 * K_A0, rel=1e-9)
    # ...e a fonte também, então a quebra dá o mesmo número de linhas.
    r4 = blocos._quebrar(TEXTO_LONGO, a4.titulo.largura * 1.6, a4.pt_titulo)
    r0 = blocos._quebrar(TEXTO_LONGO, a0.titulo.largura * 1.6, a0.pt_titulo)
    assert r4.count("\n") >= 1, "o texto de teste tem de realmente quebrar"
    assert r4.count("\n") == r0.count("\n")


def test_caixa_de_titulo_quebra_igual_em_a4_e_a0() -> None:
    """Fim a fim: a própria caixa de título, não só o helper de quebra."""

    def _conteudo(perfil):
        fig = plt.figure(figsize=perfil.figsize_pol)
        blocos.caixa_titulo(fig, perfil, TEXTO_LONGO)
        texto = fig.axes[-1].texts[0].get_text()
        plt.close(fig)
        return texto

    t4 = _conteudo(_perfil("A4"))
    t0 = _conteudo(_perfil("A0"))
    assert t4.count("\n") >= 1
    assert t4.count("\n") == t0.count("\n")


@pytest.mark.parametrize("orientacao", ("retrato", "paisagem"))
def test_caixa_de_titulo_nunca_sobe_para_fora_do_quadro(orientacao: str) -> None:
    """A caixa do título começa dentro do quadro, abaixo dos rótulos da grade.

    Regressão do Dinâmica 2008 (06/11/2026): o topo da caixa vinha do bbox do
    texto e o título saía por cima da moldura, cobrindo a longitude do topo.
    """
    perfil = perfil_pagina.obter(orientacao)
    for texto in ("Dinâmica 2008", "Ano: 2026", TEXTO_LONGO):
        plano = blocos.planejar_titulo(perfil, texto)
        assert plano.caixa.y0 >= perfil.mapa.y0, (orientacao, texto)
        assert plano.caixa.y1 <= perfil.mapa.y1, (orientacao, texto)


# --------------------------------------------------------------------------- #
# (f) caixa pequena quebra em mais linhas
# --------------------------------------------------------------------------- #


def test_caixa_pequena_quebra_em_mais_linhas() -> None:
    a4 = _perfil("A4")
    pt = a4.pt_titulo
    largo = blocos._quebrar(TEXTO_LONGO, a4.titulo.largura * 1.6, pt)
    curto = blocos._quebrar(TEXTO_LONGO, a4.titulo.largura * 0.2, pt)
    assert curto.count("\n") > largo.count("\n")
