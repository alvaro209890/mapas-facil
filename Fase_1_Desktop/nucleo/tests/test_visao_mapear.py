# F1-07 — sanitização da resposta do modelo (AP-04: nunca aceita fora do
# catálogo) e montagem da proposta (confiança < 0.7 vira pergunta, F1-07 §Limites).

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.visao import mapear
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture
def pasta_harmonia(tmp_path: Path):
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    yield tmp_path
    workspace_servico.fechar()


def _resposta(**overrides) -> str:
    base = {
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
    base.update(overrides)
    return json.dumps(base)


# --------------------------------------------------------------------------- parsear


def test_parsear_resposta_json_puro() -> None:
    dados = mapear.parsear_resposta(_resposta())
    assert dados["mapa_da_serie"] == "dinamica"


def test_parsear_resposta_cercada_em_markdown() -> None:
    bruto = f"```json\n{_resposta()}\n```"
    dados = mapear.parsear_resposta(bruto)
    assert dados["mapa_da_serie"] == "dinamica"


def test_parsear_resposta_invalida_e_ia061() -> None:
    with pytest.raises(ErroNucleo) as exc:
        mapear.parsear_resposta("isto não é JSON de jeito nenhum")
    assert exc.value.codigo == limites.CODIGO_VISAO_RESPOSTA_INVALIDA


def test_parsear_resposta_lista_nao_e_objeto() -> None:
    with pytest.raises(ErroNucleo) as exc:
        mapear.parsear_resposta("[1, 2, 3]")
    assert exc.value.codigo == limites.CODIGO_VISAO_RESPOSTA_INVALIDA


# --------------------------------------------------------------------------- sanitizar (AP-04)


def test_sanitizar_rejeita_estilo_fora_do_catalogo() -> None:
    bruto = json.loads(
        _resposta(
            camadas=[
                {
                    "legenda_lida": "Área X",
                    "cor_amostrada": "#123456",
                    "estilo_sugerido": "estilo_que_nao_existe",
                    "confianca": 0.9,
                }
            ]
        )
    )
    analise, avisos = mapear.sanitizar_resposta(bruto)
    assert analise["camadas"] == []
    assert any("estilo_que_nao_existe" in a for a in avisos)


def test_sanitizar_rejeita_mapa_da_serie_fora_do_catalogo() -> None:
    bruto = json.loads(_resposta(mapa_da_serie="serie_inventada"))
    analise, avisos = mapear.sanitizar_resposta(bruto)
    assert analise["mapa_da_serie"] is None
    assert any("serie_inventada" in a for a in avisos)


def test_sanitizar_aceita_estilo_e_serie_validos() -> None:
    bruto = json.loads(_resposta())
    analise, avisos = mapear.sanitizar_resposta(bruto)
    assert analise["mapa_da_serie"] == "dinamica"
    assert analise["camadas"][0]["estilo_sugerido"] == "perimetro_imovel"
    assert avisos == []


def test_sanitizar_confianca_fora_da_faixa_e_grampeada() -> None:
    bruto = json.loads(_resposta(confianca=1.7))
    analise, _ = mapear.sanitizar_resposta(bruto)
    assert analise["confianca"] == 1.0
    bruto2 = json.loads(_resposta(confianca=-0.3))
    analise2, _ = mapear.sanitizar_resposta(bruto2)
    assert analise2["confianca"] == 0.0


def test_sanitizar_campos_ausentes_nao_quebra() -> None:
    analise, avisos = mapear.sanitizar_resposta({})
    assert analise["mapa_da_serie"] is None
    assert analise["camadas"] == []
    assert analise["confianca"] == 0.0


# --------------------------------------------------------------------------- montar_proposta


def test_montar_proposta_confianca_alta_gera_mapspec_candidato(pasta_harmonia: Path) -> None:
    bruto = mapear.parsear_resposta(_resposta())
    analise, avisos = mapear.sanitizar_resposta(bruto)
    proposta = mapear.montar_proposta(analise=analise, avisos_sanitizacao=avisos, orientacao="retrato")
    assert proposta["mapspec_candidato"] is not None
    assert proposta["modelo_galeria_usado"] == "dinamica_2026_retrato"
    assert proposta["perguntas"] == []


def test_montar_proposta_confianca_geral_baixa_vira_pergunta_sem_mapspec(
    pasta_harmonia: Path,
) -> None:
    bruto = mapear.parsear_resposta(_resposta(confianca=0.4))
    analise, avisos = mapear.sanitizar_resposta(bruto)
    proposta = mapear.montar_proposta(analise=analise, avisos_sanitizacao=avisos, orientacao="retrato")
    assert proposta["mapspec_candidato"] is None
    assert proposta["perguntas"]
    assert "0.40" in proposta["perguntas"][0]


def test_montar_proposta_camada_confianca_baixa_vira_pergunta_mas_mapspec_ainda_sai(
    pasta_harmonia: Path,
) -> None:
    bruto = mapear.parsear_resposta(
        _resposta(
            camadas=[
                {
                    "legenda_lida": "Fazenda Harmonia",
                    "cor_amostrada": "#FFFF00",
                    "estilo_sugerido": "perimetro_imovel",
                    "confianca": 0.5,
                }
            ]
        )
    )
    analise, avisos = mapear.sanitizar_resposta(bruto)
    proposta = mapear.montar_proposta(analise=analise, avisos_sanitizacao=avisos, orientacao="retrato")
    assert proposta["mapspec_candidato"] is not None  # série com confiança alta ainda monta
    assert any("Fazenda Harmonia" in p for p in proposta["perguntas"])


def test_montar_proposta_serie_sem_modelo_de_galeria_vira_pergunta() -> None:
    analise = {
        "mapa_da_serie": "embargos",  # série real, mas sem modelo pronto na galeria
        "ano": None,
        "template_sugerido": None,
        "confianca": 0.9,
        "camadas": [],
        "metadados_lidos": [],
        "tabela_presente": False,
        "observacoes": [],
    }
    # "embargos" nem está no MAPAS_SERIE_CONHECIDOS — simula direto pra testar o
    # branch "sem candidatos" sem depender do vocabulário do prompt.
    proposta = mapear.montar_proposta(analise=analise, avisos_sanitizacao=[], orientacao=None)
    assert proposta["mapspec_candidato"] is None
    assert proposta["perguntas"]


def test_montar_proposta_sem_analise_devolve_estrutura_vazia_honesta() -> None:
    proposta = mapear.montar_proposta(analise=None, avisos_sanitizacao=["sem chave"], orientacao=None)
    assert proposta["mapspec_candidato"] is None
    assert proposta["mapa_da_serie"] is None
    assert proposta["avisos"] == ["sem chave"]


def test_montar_proposta_workspace_sem_requisito_obrigatorio_vira_pergunta(tmp_path: Path) -> None:
    """Pasta sem ATP: `montar_mapspec` levanta NU-233 — vira pergunta, não crash."""
    (tmp_path / "SHP").mkdir()
    workspace_servico.abrir(str(tmp_path))
    try:
        bruto = mapear.parsear_resposta(_resposta())
        analise, avisos = mapear.sanitizar_resposta(bruto)
        proposta = mapear.montar_proposta(
            analise=analise, avisos_sanitizacao=avisos, orientacao="retrato"
        )
        assert proposta["mapspec_candidato"] is None
        assert proposta["perguntas"]
    finally:
        workspace_servico.fechar()
