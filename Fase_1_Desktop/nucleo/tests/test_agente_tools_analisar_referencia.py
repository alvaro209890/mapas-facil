# F1-07 — `analisar_referencia` na tool real: saiu de `IA-022`, integra com H6
# (`mapspec.atualizado`) e nunca vaza WKT/CPF/caminho/chave para o prompt de visão.

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from mapasfacil_nucleo.agente import tools
from mapasfacil_nucleo.agente.contexto import assert_sem_vazamento
from mapasfacil_nucleo.agente.tools import executar
from mapasfacil_nucleo.agente.visao import servico as visao_servico
from mapasfacil_nucleo.agente.visao.provedor import ProvedorVisaoFixo
from mapasfacil_nucleo.protocolo import Emissor
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm

RESPOSTA_ALTA_CONFIANCA = json.dumps(
    {
        "mapa_da_serie": "dinamica",
        "ano": 2026,
        "template_sugerido": "dinamica_retrato",
        "confianca": 0.9,
        "camadas": [
            {
                "legenda_lida": "Fazenda Harmonia",
                "cor_amostrada": "#FFFF00",
                "estilo_sugerido": "perimetro_imovel",
                "confianca": 0.95,
            }
        ],
        "metadados_lidos": [{"rotulo": "Escala", "valor": "1:60.000"}],
        "tabela_presente": True,
        "observacoes": [],
    }
)


@pytest.fixture(autouse=True)
def _sem_provedor_pendurado():
    yield
    visao_servico.configurar_provedor(None)


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")  # tem CPF no texto do PDF
    workspace_servico.abrir(str(tmp_path))
    yield tmp_path
    workspace_servico.fechar()


def _png_bytes() -> bytes:
    img = Image.new("RGB", (630, 891), "white")
    ImageDraw.Draw(img).rectangle([0, 0, img.width - 1, img.height - 1], outline="black", width=10)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_analisar_referencia_nao_e_mais_ia022() -> None:
    r = executar("analisar_referencia", {}, {})
    assert r.get("codigo") != "IA-022"
    assert r["codigo"] == "NU-001"  # 'arquivo' obrigatório ausente


def test_analisar_referencia_esta_fora_de_tools_com_dependencia_pendente() -> None:
    assert "analisar_referencia" not in tools.TOOLS_COM_DEPENDENCIA_PENDENTE
    assert tools.TOOLS_COM_DEPENDENCIA_PENDENTE == frozenset()


def test_analisar_referencia_sem_workspace() -> None:
    workspace_servico.fechar()
    r = executar("analisar_referencia", {"arquivo": "x.png"}, {})
    assert r["codigo"] == "NU-040"


def test_analisar_referencia_arquivo_ausente(pasta: Path) -> None:
    r = executar("analisar_referencia", {"arquivo": "nao_existe.png"}, {})
    assert r["ok"] is False
    assert r["codigo"] == "NU-001"


def test_analisar_referencia_confianca_alta_atualiza_ctx_e_emite_mapspec_atualizado(
    pasta: Path,
) -> None:
    (pasta / "referencia.png").write_bytes(_png_bytes())
    visao_servico.configurar_provedor(ProvedorVisaoFixo(RESPOSTA_ALTA_CONFIANCA))

    eventos: list[dict[str, Any]] = []
    emissor = Emissor("teste", sink=eventos.append)
    ctx: dict[str, Any] = {"emissor": emissor}

    r = executar("analisar_referencia", {"arquivo": "referencia.png"}, ctx)

    assert r["ok"] is True
    assert r["mapa_da_serie"] == "dinamica"
    assert "mapspec_id" in r
    assert ctx["mapspec"]["id"] == r["mapspec_id"]
    assert ctx["mapspec_origem"] == "analisar_referencia"

    atualizados = [e for e in eventos if e["evento"] == "mapspec.atualizado"]
    assert len(atualizados) == 1
    assert atualizados[0]["dados"]["id"] == r["mapspec_id"]
    assert atualizados[0]["dados"]["versao"] == 1


def test_analisar_referencia_confianca_baixa_nao_toca_ctx_nem_emite(pasta: Path) -> None:
    resposta_baixa = json.dumps({**json.loads(RESPOSTA_ALTA_CONFIANCA), "confianca": 0.3})
    (pasta / "referencia.png").write_bytes(_png_bytes())
    visao_servico.configurar_provedor(ProvedorVisaoFixo(resposta_baixa))

    eventos: list[dict[str, Any]] = []
    emissor = Emissor("teste", sink=eventos.append)
    ctx: dict[str, Any] = {"emissor": emissor}

    r = executar("analisar_referencia", {"arquivo": "referencia.png"}, ctx)
    assert r["ok"] is True
    assert r["perguntas"]
    assert "mapspec" not in ctx
    assert eventos == []


def test_analisar_referencia_layout_fora_do_padrao_nao_inventa_template(pasta: Path) -> None:
    """F1-07 §Limites: layout fora do perfil Harmonia — recusa, não inventa."""
    resposta = json.dumps(
        {
            "mapa_da_serie": None,
            "ano": None,
            "template_sugerido": "layout_de_outro_escritorio_qualquer",
            "confianca": 0.2,
            "camadas": [],
            "metadados_lidos": [],
            "tabela_presente": False,
            "observacoes": ["layout não reconhecido"],
        }
    )
    (pasta / "referencia.png").write_bytes(_png_bytes())
    visao_servico.configurar_provedor(ProvedorVisaoFixo(resposta))

    r = executar("analisar_referencia", {"arquivo": "referencia.png"}, {})
    assert "mapspec_candidato" not in r  # nunca reexposto — tools.py move pra ctx ou descarta
    assert "mapspec_id" not in r
    assert r["mapa_da_serie"] is None
    assert r["perguntas"]


def test_prompt_de_visao_nunca_leva_wkt_cpf_caminho_ou_chave(pasta: Path) -> None:
    """Assert de vazamento (F1-06 §Testes) alinhado ao request real de visão."""
    (pasta / "referencia.png").write_bytes(_png_bytes())
    provedor = ProvedorVisaoFixo(RESPOSTA_ALTA_CONFIANCA)
    visao_servico.configurar_provedor(provedor)

    r = executar("analisar_referencia", {"arquivo": "referencia.png"}, {})
    assert r["ok"] is True
    assert provedor.chamadas, "o provedor de visão não foi chamado"

    for chamada in provedor.chamadas:
        assert_sem_vazamento(chamada["prompt"])
        assert str(pasta) not in chamada["prompt"]
        assert "sk-" not in chamada["prompt"]
