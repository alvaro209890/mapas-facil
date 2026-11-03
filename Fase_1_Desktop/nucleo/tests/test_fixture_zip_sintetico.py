"""O pacote sintético tem que ser **válido**, não só ter a forma certa.

Regressão de 03/11/2026: o `.dbf` feito à mão saía com o descritor de 31 bytes e o `.shx`
declarava 50 palavras a menos; o `workspace.abrir` do server morria em `NU-000` e o smoke
ponta a ponta não passava da importação. O fixture é insumo do núcleo — se o leitor real
recusa, o teste de integração que o usa não prova nada.
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

from mapasfacil_nucleo.workspace import servico as workspace_servico

RAIZ = Path(__file__).resolve().parents[3]
FIXTURE = RAIZ / "Fase_3_Web" / "fixtures" / "gerar_zip_sintetico.py"


def _carregar_gerador():
    if not FIXTURE.is_file():  # pragma: no cover - checkout parcial
        pytest.skip("gerar_zip_sintetico.py não está neste checkout")
    spec = importlib.util.spec_from_file_location("gerar_zip_sintetico", FIXTURE)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def pacote(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("fixture") / "imovel_ficticio.zip"
    return _carregar_gerador().gerar(destino)


def test_zip_tem_o_formato_do_pacote_do_simcar(pacote: Path) -> None:
    nomes = set(zipfile.ZipFile(pacote).namelist())
    for esperado in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        assert f"CAR/ATP{esperado}" in nomes, nomes
    assert "LEIA-ME.txt" in nomes
    assert any(n.lower().endswith(".pdf") for n in nomes)


def test_shapefile_e_lido_pelo_pyshp(pacote: Path, tmp_path: Path) -> None:
    import shapefile

    zipfile.ZipFile(pacote).extractall(tmp_path)
    leitor = shapefile.Reader(str(tmp_path / "CAR" / "ATP.shp"))
    assert len(leitor) == 1
    assert [c[0] for c in leitor.fields[1:]] == ["NOME", "classe", "area_ha"]
    assert leitor.record(0)[1] == "ARL"


def test_anel_e_no_sentido_horario(pacote: Path, tmp_path: Path) -> None:
    """Anel externo de shapefile é horário; anti-horário o leitor trata como buraco.

    Pela fórmula do laço (shoelace), horário dá soma **negativa** — o dobro da área com
    sinal trocado.
    """
    import shapefile

    zipfile.ZipFile(pacote).extractall(tmp_path)
    anel = shapefile.Reader(str(tmp_path / "CAR" / "ATP.shp")).shape(0).points
    area2 = sum(
        anel[i][0] * anel[i + 1][1] - anel[i + 1][0] * anel[i][1] for i in range(len(anel) - 1)
    )
    assert area2 < 0, f"anel anti-horário (2·área = {area2:.0f}) — vira buraco no leitor"


def test_workspace_abre_o_pacote_e_reconhece_o_recibo(pacote: Path, tmp_path: Path) -> None:
    zipfile.ZipFile(pacote).extractall(tmp_path)
    estado = workspace_servico.abrir(str(tmp_path))
    assert len(estado["workspace"]["shapefiles"]) == 1
    assert estado["recibo"] is not None, "o PDF do recibo precisa ser reconhecido pelo índice"
    assert estado["doctor"]["pronto_para_mxd"] in (True, False)
