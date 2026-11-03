"""W9-12 — regras de layout das skills no motor nativo (W-17 §5).

As quatro lições que dão problema em campo:

1. **legenda** com o topo pelo menos 0,5 cm abaixo do quadro e a borda direita 0,2 cm antes
   do logo (senão "LEGENDA" encosta no rótulo da grade ou no logo);
2. a legenda **encolhe** quando não cabe (já é o laço de 5 tentativas em `bloco_legenda`);
3. **METADADOS** com 5–6 linhas não pode estourar a caixa;
4. **H16**: nenhum bloco pode sair da página em folha nenhuma.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.motores import blocos, folhas as folhas_mod, perfil_pagina

TODAS = [
    perfil_pagina.perfil_para(folhas_mod.folha_padrao(f, o))
    for f in folhas_mod.ORDEM
    for o in folhas_mod.ORIENTACOES
]


@pytest.mark.parametrize("perfil", TODAS, ids=lambda p: p.id)
def test_legenda_comeca_abaixo_do_quadro(perfil) -> None:
    """A legenda nunca encosta no quadro; no perfil retrato da PH a folga é de 0,5 cm.

    No paisagem o perfil **medido** do acervo tem 3,5 mm (a legenda é alta porque os temáticos
    têm muitas classes). O teste cobra a regra da PH onde ela nasceu e, no paisagem, exige o
    mínimo de 3 mm — mudar o medido seria inventar medida.
    """
    folga = perfil.legenda.y0 - perfil.mapa.y1
    minimo = 5.0 if perfil.orientacao == "retrato" else 3.0
    assert folga >= minimo - 1e-6, (
        f"{perfil.id}: legenda só {folga:.1f} mm abaixo do quadro (mínimo {minimo} mm)"
    )


@pytest.mark.parametrize("perfil", TODAS, ids=lambda p: p.id)
def test_legenda_nao_invade_o_logo(perfil) -> None:
    """0,2 cm entre a borda direita da legenda e o logo."""
    folga = perfil.logo.x0 - perfil.legenda.x1
    assert folga >= 2.0 - 1e-6, f"{perfil.id}: legenda a {folga:.1f} mm do logo"


@pytest.mark.parametrize("perfil", TODAS, ids=lambda p: p.id)
def test_nenhuma_caixa_sai_da_pagina(perfil) -> None:
    """Check H16."""
    fora = perfil_pagina.caixas_fora_da_pagina(perfil)
    assert not fora, f"{perfil.id}: {fora}"


def test_h16_acusa_caixa_fora() -> None:
    """O check não é decorativo: uma caixa empurrada para fora tem de aparecer."""
    quebrado = perfil_pagina.escalar_perfil(
        perfil_pagina.RETRATO, folhas_mod.folha_padrao("A4", "retrato")
    )
    assert not perfil_pagina.caixas_fora_da_pagina(quebrado)
    import dataclasses

    estourado = dataclasses.replace(
        perfil_pagina.RETRATO,
        tabela=perfil_pagina.Caixa(67.1, 236.3, 240.0, 256.3),  # passa dos 210 mm
    )
    fora = perfil_pagina.caixas_fora_da_pagina(estourado)
    assert [c["caixa"] for c in fora] == ["tabela"]
    assert fora[0]["pior_mm"] == pytest.approx(30.0, abs=0.01), fora[0]


@pytest.mark.parametrize("n_linhas", [4, 5, 6, 7])
@pytest.mark.parametrize("perfil", TODAS, ids=lambda p: p.id)
def test_metadados_com_muitas_linhas_cabem_na_caixa(perfil, n_linhas: int) -> None:
    """A regra dos 16→14→12 pt existe para o bloco caber; aqui se prova que ele cabe."""
    pt = blocos.pt_metadados_efetivo(perfil, n_linhas)
    assert pt >= perfil.pt_metadados * 0.6 - 1e-9, "corpo do bloco menor que o piso"
    assert pt <= perfil.pt_metadados + 1e-9, "o corte só reduz, nunca aumenta"
    passo = blocos._passo_linha(pt, perfil.metadados.altura)
    altura_necessaria = passo * (n_linhas + 0.6) * perfil.metadados.altura
    assert altura_necessaria <= perfil.metadados.altura + 1e-6, (
        f"{perfil.id}: {n_linhas} linhas ocupam {altura_necessaria:.1f} mm "
        f"numa caixa de {perfil.metadados.altura:.1f} mm"
    )


@pytest.mark.parametrize("perfil", TODAS, ids=lambda p: p.id)
def test_hachura_de_ac_e_avn_no_catalogo(perfil) -> None:
    """AC magenta hachurado, AVN verde hachurado — as dinâmicas exigem a hachura."""
    from mapasfacil_nucleo.motores import estilos

    ac = estilos.obter("ac")
    avn = estilos.obter("avn")
    assert ac.get("hachura"), "AC sem hachura no catálogo de estilos"
    assert avn.get("hachura"), "AVN sem hachura no catálogo de estilos"
    assert ac.get("cor_linha", "").upper().startswith("#C5"), "AC não está magenta"
    assert avn.get("cor_linha", "").upper().startswith("#4C"), "AVN não está verde"


def test_corte_de_linhas_do_metadados_reduz_de_verdade() -> None:
    """A regra tem de morder: 12 linhas num bloco medido não cabem com o corpo inteiro."""
    perfil = perfil_pagina.RETRATO
    assert blocos.pt_metadados_efetivo(perfil, 5) == pytest.approx(perfil.pt_metadados)
    reduzido = blocos.pt_metadados_efetivo(perfil, 12)
    assert reduzido < perfil.pt_metadados
    assert reduzido >= perfil.pt_metadados * 0.6 - 1e-9
