"""W7 — integração: um job real emite o palco na ordem, com arquivos de verdade.

Não é teste de contrato (esse é `test_motion_contrato.py`) nem de desenho: aqui roda
`gerar_mapa` de ponta a ponta num projeto sintético e confere que os três eventos do palco
aparecem como o plano W-03 promete, com GeoJSON gravado sob `Mapas/.preview/<job>/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo import motion
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.progresso import RastreadorProgresso
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm

JOB = "01JOBPALCO0000000000000000"


@pytest.fixture
def projeto(tmp_path: Path) -> dict[str, Any]:
    for nome in ("Mapas", "SHP", "MXD", "_extraido"):
        (tmp_path / nome).mkdir(parents=True, exist_ok=True)
    escrever_shapefile_quadrado_utm(tmp_path / "Dados" / "ATP.shp", nome="Harmonia", lado_m=4000)
    escrever_shapefile_quadrado_utm(tmp_path / "Dados" / "AVN.shp", nome="AVN", lado_m=1500)
    from mapasfacil_nucleo.fsguard import WorkspaceGuard

    guard = WorkspaceGuard(tmp_path)
    mapspec = {
        "contract_version": 2,
        "perfil": "harmonia",
        "id": "spec_palco",
        "versao": 1,
        "titulo": "Dinâmica 2026",
        "template": "dinamica_retrato",
        "saidas": ["pdf"],
        "imovel": {
            "nome": "Fazenda Harmonia",
            "car": "MT102042/2017",
            "municipio": {"nome": "Vila Rica", "uf": "MT"},
            "geometria": "local.ATP",
        },
        "crs": "EPSG:31982",
        "escala": "auto",
        "camadas": [
            {
                "id": "perimetro",
                "nome_no_mxd": "Fazenda Harmonia",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
            },
            {
                "id": "avn",
                "nome_no_mxd": "Área de vegetação nativa",
                "fonte": "local.AVN",
                "estilo": "avn",
                "ordem": 30,
            },
        ],
        "elementos_layout": {"tabela": False, "minimapa": False},
        # O pacote da web SEMPRE tem SHP/ (D-decisão): é de lá que sai o GeoJSON do palco.
        "saida": {"pasta": "Mapas", "nome_base": "Dinamica", "materializar_camadas_em": "SHP"},
    }
    return {
        "guard": guard,
        "mapspec": mapspec,
        "fontes_idx": {
            "ATP": str(tmp_path / "Dados" / "ATP.shp"),
            "AVN": str(tmp_path / "Dados" / "AVN.shp"),
        },
        "raiz": tmp_path,
    }


@pytest.fixture
def eventos(projeto: dict[str, Any]) -> list[dict[str, Any]]:
    coletados: list[dict[str, Any]] = []
    prog = RastreadorProgresso(
        lambda evento, dados: coletados.append({"evento": evento, **dados}), job_id=JOB
    )
    gerar_mapa(
        projeto["mapspec"],
        projeto["guard"],
        projeto["fontes_idx"],
        progresso=prog,
    )
    return coletados


def _de(eventos: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [e for e in eventos if e["evento"] == nome]


def test_foco_do_viewport_na_ordem_do_job(eventos: list[dict[str, Any]]) -> None:
    niveis = [e["nivel"] for e in _de(eventos, motion.EVENTO_VIEWPORT)]
    assert "imovel" in niveis
    assert niveis.index("imovel") < niveis.index("enquadramento") < niveis.index("folha")
    # A câmera nunca volta atrás dentro do mesmo job.
    indices = [motion.NIVEIS_VIEWPORT.index(n) for n in niveis]
    assert indices == sorted(indices)


def test_foco_de_enquadramento_traz_escala_e_quadro(eventos: list[dict[str, Any]]) -> None:
    foco = next(
        e for e in _de(eventos, motion.EVENTO_VIEWPORT) if e["nivel"] == "enquadramento"
    )
    assert foco["escala"] is None or foco["escala"] > 0
    assert str(foco["crs_mapa"]).startswith("EPSG:")
    assert foco["quadro_mm"]["largura"] > 0 and foco["quadro_mm"]["altura"] > 0


def test_camadas_acendem_na_ordem_de_pintura(eventos: list[dict[str, Any]]) -> None:
    camadas = _de(eventos, motion.EVENTO_CAMADA)
    papeis = [c["papel"] for c in camadas]
    assert papeis[:2] == ["perimetro", "avn"]
    assert [c["sequencia"] for c in camadas] == list(range(1, len(camadas) + 1))
    for camada in camadas:
        assert camada["job_id"] == JOB
        assert camada["area_ha"] is None or camada["area_ha"] > 0


def test_geojson_do_palco_existe_e_e_simplificado(eventos: list[dict[str, Any]], projeto) -> None:
    camada = next(e for e in _de(eventos, motion.EVENTO_CAMADA) if e["papel"] == "avn")
    caminho = projeto["raiz"] / camada["caminho"]
    assert caminho.is_file(), camada["caminho"]
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["type"] == "FeatureCollection"
    assert dados["features"]
    # Coordenadas em graus (4326), não em metros da UTM.
    x = dados["features"][0]["geometry"]["coordinates"][0][0][0]
    assert -180 <= x <= 180


def test_layout_elemento_cobre_os_ligados(eventos: list[dict[str, Any]]) -> None:
    elementos = [e["elemento"] for e in _de(eventos, motion.EVENTO_LAYOUT)]
    assert elementos, "o job não posicionou nenhum elemento"
    assert len(set(elementos)) == len(elementos), "elemento repetido na montagem"
    assert "titulo_caixa" in elementos
    assert elementos == motion.elementos_na_ordem(elementos)


def test_nenhum_evento_de_palco_traz_caminho_absoluto(eventos: list[dict[str, Any]]) -> None:
    for evento in eventos:
        caminho = evento.get("caminho")
        if not caminho:
            continue
        assert not str(caminho).startswith(("/", "C:", "c:")), caminho
        assert ".." not in str(caminho)
        if evento["evento"] in (motion.EVENTO_CAMADA, motion.EVENTO_LAYOUT):
            assert str(caminho).startswith(f"Mapas/.preview/{JOB}/")


def test_sem_canal_de_eventos_nada_e_gravado(projeto) -> None:
    resultado = gerar_mapa(projeto["mapspec"], projeto["guard"], projeto["fontes_idx"])
    assert resultado["pdf"].endswith(".pdf")
    assert not (projeto["raiz"] / "Mapas" / ".preview").exists()
