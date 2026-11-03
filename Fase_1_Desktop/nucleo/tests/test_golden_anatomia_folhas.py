"""W9-08 — golden de anatomia por folha: A4 medido, A3 e A0 derivados (D31).

O gabarito continua sendo **um**: a anatomia medida na A4. A3/A0 não têm perfil novo medido à
mão — são o mesmo desenho × `k`, e é isso que este teste confere no PDF de verdade, com o
check H15 (papel exato) junto.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from mapasfacil_nucleo.motores import folhas as folhas_mod
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.validacao import anatomia
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import montar_workspace_minimo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
FOLHAS = ("A4", "A3", "A0")


@pytest.fixture(scope="module")
def anatomias(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    """Renderiza a mesma dinâmica em A4, A3 e A0 uma vez e mede as três anatomias."""
    tmp = tmp_path_factory.mktemp("golden_folhas")
    montar_workspace_minimo(tmp)
    workspace_servico.abrir(str(tmp))
    estado = workspace_servico.estado_atual()
    assert estado is not None

    spec_base = json.loads(
        (REPO / "shared/fixtures/mapspecs/dinamica_2026_canonico.json").read_text(encoding="utf-8")
    )
    medidas: dict[str, dict] = {}
    for formato in FOLHAS:
        spec = copy.deepcopy(spec_base)
        spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
        spec["basemap"] = {"tipo": "nenhum"}
        spec["saidas"] = ["pdf"]
        spec["elementos_layout"]["tabela"] = False
        spec["folha"] = {
            "formato": formato,
            "orientacao": "retrato",
            "escala_elementos": "proporcional",
        }
        spec["saida"] = {
            "pasta": "Mapas",
            "nome_base": f"golden_{formato}",
            "caminhos_relativos": True,
        }
        resultado = gerar_mapa(spec, estado.guard, workspace_servico.fontes_idx(estado))
        medidas[formato] = anatomia.medir(tmp / resultado["pdf"])
    return medidas


@pytest.mark.parametrize("formato", FOLHAS)
def test_h15_papel_exato_em_toda_folha(anatomias: dict[str, dict], formato: str) -> None:
    check = anatomia.conferir_folha(anatomias[formato], folhas_mod.folha_padrao(formato, "retrato"))
    assert check["ok"], check["mensagem"]
    assert abs(check["delta_mm"]["largura"]) <= 1.0
    assert abs(check["delta_mm"]["altura"]) <= 1.0


@pytest.mark.parametrize("formato", ("A3", "A0"))
def test_anatomia_derivada_confere_com_o_a4_vezes_k(anatomias: dict[str, dict], formato: str) -> None:
    folha = folhas_mod.folha_padrao(formato, "retrato")
    k = folhas_mod.fator_k(formato)
    esperada = anatomia.esperada_para_folha(anatomias["A4"], folha)
    resultado = anatomia.comparar(esperada, anatomias[formato], tolerancia_mm=6.0, fator=k)
    assert resultado["ok"], f"{formato}: {resultado['falhas']}"
    assert resultado["tolerancia_mm"] == pytest.approx(6.0 * k, abs=1e-3)


def test_grade_acompanha_a_folha_sem_multiplicar_rotulos(anatomias: dict[str, dict]) -> None:
    """A grade ganha segmentos maiores, não mais rótulos: 4–8 por eixo em qualquer papel."""
    for formato in FOLHAS:
        bordas = anatomias[formato]["rotulos_dms"]["por_borda"]
        for borda, n in bordas.items():
            assert 1 <= n <= 8, f"{formato}: {n} rótulos na borda {borda} (o padrão pede até 8)"
        assert sum(bordas.values()) <= 32, f"{formato} com grade densa demais: {bordas}"


def test_metadados_e_legenda_continuam_no_rodape(anatomias: dict[str, dict]) -> None:
    """Em A0 o bloco de metadados não pode "subir" para dentro do quadro do mapa."""
    for formato in FOLHAS:
        medida = anatomias[formato]
        quadro = medida["quadro_mapa"]
        assert quadro, f"{formato}: quadro do mapa não detectado"
        for bloco in ("metadados", "legenda"):
            caixa = medida[bloco]
            assert caixa, f"{formato}: {bloco} não detectado"
            assert caixa["y0"] >= quadro["y1"] - 1.0, (
                f"{formato}: {bloco} começou acima da base do quadro "
                f"({caixa['y0']:.1f} < {quadro['y1']:.1f})"
            )


def test_titulo_cabe_no_topo_em_toda_folha(anatomias: dict[str, dict]) -> None:
    for formato in FOLHAS:
        caixa = (anatomias[formato].get("titulo") or {}).get("caixa_mm")
        assert caixa, f"{formato}: título não detectado"
        assert caixa["y1"] <= anatomias[formato]["pagina_mm"]["altura"] * 0.35


def test_pdf_de_folha_maior_nao_estoura_de_tamanho(anatomias: dict[str, dict]) -> None:
    """Sem basemap o PDF é vetorial: A0 não pode ser ordem de grandeza maior que a A4."""
    tamanho = {f: Path(anatomias[f]["pdf"]).stat().st_size for f in FOLHAS}
    assert tamanho["A0"] <= tamanho["A4"] * 4 + 200_000, tamanho


if __name__ == "__main__":  # pragma: no cover - conveniência de depuração
    sys.exit(pytest.main([__file__, "-q"]))
