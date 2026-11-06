"""W9-08 — anatomia esperada por folha (A4 × k) e o check H15.

O gabarito é um só: a anatomia medida na A4. Toda folha maior é o mesmo desenho
multiplicado por `k`; o que se confere num PDF de A0 é a mesma coisa que se confere na A4,
só que com a tolerância também multiplicada — senão 6 mm de folga viram intolerância zero.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo.motores import folhas as folhas_mod
from mapasfacil_nucleo.validacao import anatomia

GOLDEN_A4 = {
    "pagina_mm": {"largura": 210.0, "altura": 297.0},
    "orientacao": "retrato",
    "quadro_mapa": {"x0": 7.0, "y0": 5.0, "x1": 203.5, "y1": 257.0},
    "titulo": {"caixa_mm": {"x0": 61.98, "y0": 7.11, "x1": 134.55, "y1": 21.68}, "texto": "DINÂMICA 2026"},
    "metadados": {"x0": 64.9, "y0": 265.2, "x1": 120.0, "y1": 291.2},
    "legenda": {"x0": 131.8, "y0": 266.0, "x1": 172.0, "y1": 295.0},
    "rotulos_dms": {"total": 18, "por_borda": {"superior": 5, "inferior": 5, "esquerda": 4, "direita": 4}},
}


def test_a4_esperada_e_a_propria_golden() -> None:
    esperada = anatomia.esperada_para_folha(GOLDEN_A4, folhas_mod.folha_padrao("A4", "retrato"))
    assert esperada["fator"] == pytest.approx(1.0)
    assert esperada["pagina_mm"] == {"largura": 210.0, "altura": 297.0}
    for chave in ("quadro_mapa", "metadados", "legenda"):
        assert esperada[chave] == GOLDEN_A4[chave]
    assert esperada["titulo"]["caixa_mm"] == GOLDEN_A4["titulo"]["caixa_mm"]
    assert esperada["titulo"]["texto"] == "DINÂMICA 2026"


@pytest.mark.parametrize("formato", folhas_mod.ORDEM[1:])
def test_folha_maior_e_a_a4_vezes_k(formato: str) -> None:
    esperada = anatomia.esperada_para_folha(GOLDEN_A4, folhas_mod.folha_padrao(formato, "retrato"))
    k = folhas_mod.fator_k(formato)
    assert esperada["fator"] == pytest.approx(k, rel=1e-12)
    assert esperada["pagina_mm"] == {
        "largura": folhas_mod.FORMATOS[formato][0],
        "altura": folhas_mod.FORMATOS[formato][1],
    }
    for chave in ("quadro_mapa", "metadados", "legenda"):
        for campo, valor in GOLDEN_A4[chave].items():
            assert esperada[chave][campo] == pytest.approx(valor * k, abs=0.011), f"{chave}.{campo}"
    assert esperada["titulo"]["caixa_mm"]["x1"] == pytest.approx(134.55 * k, abs=0.011)


@pytest.mark.parametrize("formato", folhas_mod.ORDEM[1:])
def test_contagem_de_dms_nao_escala(formato: str) -> None:
    """4–8 rótulos por eixo em qualquer folha (W9-04): a grade não "multiplica" com o papel."""
    esperada = anatomia.esperada_para_folha(GOLDEN_A4, folhas_mod.folha_padrao(formato, "retrato"))
    assert esperada["rotulos_dms"] == GOLDEN_A4["rotulos_dms"]


def test_titulo_sem_caixa_nao_quebra() -> None:
    golden = dict(GOLDEN_A4)
    golden["titulo"] = {"caixa_mm": None, "texto": ""}
    esperada = anatomia.esperada_para_folha(golden, folhas_mod.folha_padrao("A2", "retrato"))
    assert esperada["titulo"]["caixa_mm"] is None


def test_golden_original_nao_e_modificado() -> None:
    antes = dict(GOLDEN_A4["quadro_mapa"])
    anatomia.esperada_para_folha(GOLDEN_A4, folhas_mod.folha_padrao("A0", "retrato"))
    assert GOLDEN_A4["quadro_mapa"] == antes


# --- H15 -------------------------------------------------------------------------


@pytest.mark.parametrize("formato", folhas_mod.ORDEM)
@pytest.mark.parametrize("orientacao", folhas_mod.ORIENTACOES)
def test_h15_aprova_a_pagina_certa(formato: str, orientacao: str) -> None:
    largura, altura = folhas_mod.folha_mm(formato, orientacao)
    medida = {"pagina_mm": {"largura": largura, "altura": altura}}
    check = anatomia.conferir_folha(medida, folhas_mod.folha_padrao(formato, orientacao))
    assert check["id"] == "H15"
    assert check["ok"], check["mensagem"]
    assert check["delta_mm"] == {"largura": 0.0, "altura": 0.0}


def test_h15_reprova_a4_quando_pedido_a0() -> None:
    medida = {"pagina_mm": {"largura": 210.0, "altura": 297.0}}
    check = anatomia.conferir_folha(medida, folhas_mod.folha_padrao("A0", "retrato"))
    assert not check["ok"]
    assert "fora do papel" in check["mensagem"]


def test_h15_detecta_orientacao_trocada() -> None:
    medida = {"pagina_mm": {"largura": 210.0, "altura": 297.0}}
    check = anatomia.conferir_folha(medida, folhas_mod.folha_padrao("A4", "paisagem"))
    assert not check["ok"]
    assert "orientação" in check["mensagem"]


def test_h15_tolerancia_de_1mm() -> None:
    quase = {"pagina_mm": {"largura": 297.6, "altura": 419.4}}
    assert anatomia.conferir_folha(quase, folhas_mod.folha_padrao("A3", "retrato"))["ok"]
    fora = {"pagina_mm": {"largura": 297.6, "altura": 421.5}}
    assert not anatomia.conferir_folha(fora, folhas_mod.folha_padrao("A3", "retrato"))["ok"]


def test_h15_sem_pagina_medida_e_falha_explicita() -> None:
    check = anatomia.conferir_folha({}, folhas_mod.folha_padrao("A4", "retrato"))
    assert not check["ok"]
    assert "0.0×0.0" in check["mensagem"]


# --- comparar() com tolerância escalada ------------------------------------------


def _anatomia_quase_igual(deslocamento_mm: float) -> dict:
    def _mover(caixa: dict[str, float]) -> dict[str, float]:
        return {k: v + deslocamento_mm for k, v in caixa.items()}

    return {
        "pagina_mm": {"largura": 210.0, "altura": 297.0},
        "orientacao": "retrato",
        "quadro_mapa": _mover(GOLDEN_A4["quadro_mapa"]),
        "titulo": {"caixa_mm": _mover(GOLDEN_A4["titulo"]["caixa_mm"]), "texto": "DINÂMICA 2026"},
        "metadados": _mover(GOLDEN_A4["metadados"]),
        "legenda": _mover(GOLDEN_A4["legenda"]),
        "rotulos_dms": GOLDEN_A4["rotulos_dms"],
    }


def _deslocar(anat: dict, mm: float) -> dict:
    """Copia da anatomia com o quadro e os blocos deslocados `mm` (no papel da própria anatomia)."""
    def _mover(caixa: dict[str, float] | None) -> dict[str, float] | None:
        return None if not caixa else {k: round(v + mm, 2) for k, v in caixa.items()}

    copia = dict(anat)
    copia["quadro_mapa"] = _mover(anat.get("quadro_mapa"))
    copia["metadados"] = _mover(anat.get("metadados"))
    copia["legenda"] = _mover(anat.get("legenda"))
    copia["titulo"] = {**anat["titulo"], "caixa_mm": _mover(anat["titulo"].get("caixa_mm"))}
    return copia


def test_tolerancia_escala_com_o_papel() -> None:
    """20 mm de desvio reprovam em A4 e passam em A0 — a tolerância é 6 mm × k ≈ 24 mm."""
    em_a4 = anatomia.comparar(GOLDEN_A4, _deslocar(GOLDEN_A4, 20.0), tolerancia_mm=6.0, fator=1.0)
    assert not em_a4["ok"] and "A01" in em_a4["falhas"]

    folha_a0 = folhas_mod.folha_padrao("A0", "retrato")
    k_a0 = folhas_mod.fator_k("A0")
    esperada_a0 = anatomia.esperada_para_folha(GOLDEN_A4, folha_a0)
    em_a0 = anatomia.comparar(
        esperada_a0, _deslocar(esperada_a0, 20.0), tolerancia_mm=6.0, fator=k_a0
    )
    assert em_a0["tolerancia_mm"] == pytest.approx(6.0 * k_a0, abs=1e-3)
    assert em_a0["ok"], em_a0["falhas"]

    # 30 mm passam da tolerância de A0: o teste não é complacente
    longe = anatomia.comparar(
        esperada_a0, _deslocar(esperada_a0, 30.0), tolerancia_mm=6.0, fator=k_a0
    )
    assert not longe["ok"] and "A01" in longe["falhas"]
