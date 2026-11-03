"""W7-10 — o roteiro gravado (`servidor/tests/roteiros/palco_dinamica.ndjson`) é reprojetável.

Este teste é a rede de segurança do contrato: se o emissor mudar um campo, o roteiro antigo tem de
continuar passando pelo validador do `motion`. Se não passar, ou o campo novo é incompatível (bug)
ou o roteiro precisa ser regravado de propósito — nos dois casos, alguém tem de decidir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo import motion

ROTEIRO = (
    Path(__file__).resolve().parents[3]
    / "Fase_3_Web"
    / "servidor"
    / "tests"
    / "roteiros"
    / "palco_dinamica.ndjson"
)


@pytest.mark.skipif(not ROTEIRO.is_file(), reason="roteiro ainda não gravado (gerar_palco.py)")
def test_roteiro_regravavel_repassa_pelo_contrato() -> None:
    linhas = [json.loads(l) for l in ROTEIRO.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert linhas, "roteiro vazio"
    assert [l["seq"] for l in linhas] == list(range(1, len(linhas) + 1))

    niveis: list[str] = []
    for linha in linhas:
        evento, dados = linha["evento"], dict(linha["dados"])
        if evento == motion.EVENTO_VIEWPORT:
            montado = motion.montar_dados_viewport(
                dados["nivel"],
                dados["bbox_4326"],
                dados["rotulo"],
                dados["origem"],
                job_id=dados.get("job_id"),
                etapa=dados.get("etapa"),
                escala=dados.get("escala"),
                crs_mapa=dados.get("crs_mapa"),
                quadro_mm=dados.get("quadro_mm"),
                nivel_anterior=niveis[-1] if niveis else None,
            )
            niveis.append(montado["nivel"])
        elif evento == motion.EVENTO_CAMADA:
            motion.montar_dados_camada(
                dados["camada_id"],
                dados["papel"],
                dados["nome"],
                dados["geometria"],
                sequencia=dados["sequencia"],
                total=dados["total"],
                caminho=dados["caminho"],
                job_id=dados.get("job_id"),
                etapa=dados.get("etapa"),
                bbox=dados.get("bbox_4326"),
                estilo=dados.get("estilo"),
                n_feicoes=dados.get("n_feicoes", 0),
                area_ha=dados.get("area_ha"),
            )
        elif evento == motion.EVENTO_LAYOUT:
            motion.montar_dados_layout(
                dados["elemento"],
                sequencia=dados["sequencia"],
                total=dados["total"],
                folha=dados["folha"],
                caixa_mm=dados["caixa_mm"],
                job_id=dados.get("job_id"),
                etapa=dados.get("etapa"),
                caminho=dados.get("caminho"),
                conteudo=dados.get("conteudo"),
            )

    assert niveis[:3] == ["estado", "municipio", "imovel"]
    assert niveis[-2:] == ["enquadramento", "folha"]


@pytest.mark.skipif(not ROTEIRO.is_file(), reason="roteiro ainda não gravado")
def test_assets_do_roteiro_existem_ao_lado() -> None:
    """O evento aponta para um arquivo que o teste de replay vai servir."""
    pasta = ROTEIRO.parent / "palco_dinamica"
    linhas = [json.loads(l) for l in ROTEIRO.read_text(encoding="utf-8").splitlines() if l.strip()]
    referenciados = 0
    for linha in linhas:
        caminho = (linha["dados"] or {}).get("caminho") or ""
        # Só os assets do PALCO (dentro de `<job>/`): os `preview_png` (`Mapas/.preview/parcial_01.png`)
        # saem pela rota de artefato do W6, não por esta.
        partes = caminho.split("/")
        if len(partes) < 5 or partes[:2] != ["Mapas", ".preview"]:
            continue
        resto = "/".join(partes[3:])
        assert (pasta / resto).is_file(), f"falta o asset {resto}"
        referenciados += 1
    assert referenciados >= 2
