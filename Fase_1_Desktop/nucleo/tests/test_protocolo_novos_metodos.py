from __future__ import annotations

import json

import pytest

from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_pdf_cor_solido, montar_workspace_minimo


@pytest.fixture
def projeto(tmp_path):
    montar_workspace_minimo(tmp_path)
    return tmp_path


def test_ndjson_quantitativos_calcular(projeto, mapspec_canonico) -> None:
    workspace_servico.abrir(str(projeto))
    roteador = criar_roteador()
    spec = dict(mapspec_canonico)
    spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
    req = json.dumps(
        {
            "v": 1,
            "id": "t1",
            "tipo": "req",
            "metodo": "quantitativos.calcular",
            "params": {"mapspec": spec},
        },
        ensure_ascii=False,
    )
    resposta = json.loads(processar_linha(req, roteador))
    assert resposta["tipo"] == "res"
    assert resposta["resultado"]["linhas"][0][0] == "Fazenda Harmonia"


def test_ndjson_validacao_comparar_pdf(projeto) -> None:
    workspace_servico.abrir(str(projeto))
    ref = projeto / "Mapas" / "ref.pdf"
    ger = projeto / "Mapas" / "ger.pdf"
    escrever_pdf_cor_solido(ref, rgb=(0, 128, 0))
    escrever_pdf_cor_solido(ger, rgb=(0, 128, 0))

    roteador = criar_roteador()
    req = json.dumps(
        {
            "v": 1,
            "id": "t2",
            "tipo": "req",
            "metodo": "validacao.comparar_pdf",
            "params": {
                "gerado": "Mapas/ger.pdf",
                "referencia": "Mapas/ref.pdf",
                "dpi": 72,
            },
        }
    )
    resposta = json.loads(processar_linha(req, roteador))
    assert resposta["tipo"] == "res"
    assert resposta["resultado"]["ok"] is True


def test_ndjson_mapspec_diff(mapspec_canonico) -> None:
    import copy

    roteador = criar_roteador()
    depois = copy.deepcopy(mapspec_canonico)
    depois["titulo"] = "Outro título"
    req = json.dumps(
        {
            "v": 1,
            "id": "t3",
            "tipo": "req",
            "metodo": "mapspec.diff",
            "params": {"antes": mapspec_canonico, "depois": depois},
        },
        ensure_ascii=False,
    )
    resposta = json.loads(processar_linha(req, roteador))
    assert resposta["tipo"] == "res"
    assert resposta["resultado"]["total"] >= 1


def test_ndjson_quantitativos_exportar_xlsx(projeto, mapspec_canonico) -> None:
    workspace_servico.abrir(str(projeto))
    roteador = criar_roteador()
    spec = dict(mapspec_canonico)
    spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
    spec["saida"] = {"pasta": "Mapas", "nome_base": "Export_teste"}
    req = json.dumps(
        {
            "v": 1,
            "id": "t4",
            "tipo": "req",
            "metodo": "quantitativos.exportar_xlsx",
            "params": {"mapspec": spec},
        },
        ensure_ascii=False,
    )
    resposta = json.loads(processar_linha(req, roteador))
    assert resposta["tipo"] == "res"
    assert (projeto / resposta["resultado"]["xlsx"]).exists()
