"""W9-07 — o PNG da tabela acompanha a folha (S10: ≥ 400 dpi efetivos no papel).

A tabela é imagem, não vetor: em A0 a caixa da tabela é ~6× a da A4. Se o PNG continuar com
3210 px, ele imprime a ~100 dpi e borra. O teste mede o dpi **efetivo** (pixels ÷ largura em
polegadas no papel), que é o que o `S10` confere.
"""

from __future__ import annotations

import pytest
from PIL import Image

from mapasfacil_nucleo.quantitativos import png_tabela

DADOS = {
    "colunas": ["Classe", "Área (ha)"],
    "linhas": [["AVN", 12.3456], ["AC", 1.2345], ["AUAS", 0.5]],
    "total_geral": 14.0801,
}


def _render(tmp_path, largura_cm=None, dados=None):
    destino = tmp_path / "tabela.png"
    meta = png_tabela.renderizar_png_tabela(dados or DADOS, destino, largura_cm=largura_cm)
    return meta, destino


def test_a4_mantem_o_padrao_de_3210_px(tmp_path) -> None:
    meta, destino = _render(tmp_path)
    assert meta["largura_px"] == 3211
    assert meta["dpi_efetivo"] >= 600
    assert meta["ok_dpi"] is True
    with Image.open(destino) as img:
        assert img.size[0] == meta["largura_px"]


@pytest.mark.parametrize(
    "largura_cm,minimo_px",
    [(20.3, 4700), (40.0, 9400), (81.483, 19000)],
)
def test_tabela_maior_ganha_pixels_para_manter_o_dpi(tmp_path, largura_cm, minimo_px) -> None:
    meta, _ = _render(tmp_path, largura_cm=largura_cm)
    assert meta["largura_px"] >= minimo_px
    assert meta["dpi_efetivo"] >= 590, "perdeu resolução no papel"
    assert meta["ok_dpi"] is True


def test_dpi_efetivo_independe_da_folha(tmp_path) -> None:
    a4, _ = _render(tmp_path, None)
    grande, _ = _render(tmp_path, largura_cm=81.483)
    assert abs(grande["dpi_efetivo"] - a4["dpi_efetivo"]) < 5.0


def test_teto_de_memoria_reduz_e_avisa(tmp_path) -> None:
    """A0 com 22 classes estouraria 400 MB de RGB: entra o teto e o aviso, não o OOM."""
    muitos = {
        "colunas": ["Classe", "Área (ha)"],
        "linhas": [[f"Classe {i}", round(i * 0.75, 4)] for i in range(22)],
        "total_geral": 100.0,
    }
    meta, _ = _render(tmp_path, largura_cm=81.483, dados=muitos)
    assert meta["largura_px"] * meta["altura_px"] <= png_tabela.MAXIMO_PIXELS * 1.01
    assert meta["ok_dpi"] is False, "deveria sinalizar dpi abaixo de 400 para o NU-123"


def test_altura_acompanha_o_numero_de_linhas(tmp_path) -> None:
    poucas, _ = _render(tmp_path / "p", dados=DADOS)
    muitas_dados = {**DADOS, "linhas": DADOS["linhas"] * 5}
    muitas, _ = _render(tmp_path / "m", dados=muitas_dados)
    assert muitas["altura_px"] > poucas["altura_px"]


def test_png_declara_o_dpi_nos_metadados(tmp_path) -> None:
    meta, destino = _render(tmp_path)
    with Image.open(destino) as img:
        dpi = img.info.get("dpi")
    assert dpi is not None
    assert abs(dpi[0] - meta["dpi"]) <= 1
