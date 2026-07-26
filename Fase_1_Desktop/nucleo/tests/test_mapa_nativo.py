from __future__ import annotations

import copy
import json
from pathlib import Path

import fitz
import pytest

from mapasfacil_nucleo.__main__ import processar_linha
from mapasfacil_nucleo.protocolo import envelope_req
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import eventos_e_resposta, montar_workspace_minimo


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    montar_workspace_minimo(tmp_path)
    return tmp_path


@pytest.fixture
def mapspec_minimo(repo_root: Path) -> dict:
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    spec = json.loads(caminho.read_text(encoding="utf-8"))
    spec = copy.deepcopy(spec)
    spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
    spec["saidas"] = ["pdf"]
    spec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "Dinamica_2026_teste",
        "caminhos_relativos": True,
        "materializar_camadas_em": "SHP",
    }
    return spec


def test_mapa_gerar_pdf_e_validacao(projeto: Path, mapspec_minimo: dict) -> None:
    workspace_servico.abrir(str(projeto))
    linha_abrir = json.dumps(envelope_req("workspace.abrir", {"caminho": str(projeto)}))
    processar_linha(linha_abrir)

    linha = json.dumps(envelope_req("mapa.gerar", {"mapspec": mapspec_minimo}))
    _eventos, resposta = eventos_e_resposta(processar_linha(linha))
    assert resposta["ok"] is True, resposta
    pdf_rel = resposta["resultado"]["pdf"]
    pdf_path = projeto / pdf_rel
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500

    validacao_path = projeto / resposta["resultado"]["artefatos"]["validacao"]
    assert validacao_path.exists()
    relatorio = json.loads(validacao_path.read_text(encoding="utf-8"))
    assert relatorio["motor"] == "nativo"
    assert relatorio["resumo"]["aprovado"] is True

    doc = fitz.open(pdf_path)
    assert doc.page_count == 1
    doc.close()


def test_car_ler_recibo_ndjson(projeto: Path) -> None:
    linha_abrir = json.dumps(envelope_req("workspace.abrir", {"caminho": str(projeto)}))
    processar_linha(linha_abrir)
    linha = json.dumps(
        envelope_req("car.ler_recibo", {"pdf": "CAR - Emitido.pdf"}),
    )
    resposta = json.loads(processar_linha(linha))
    assert resposta["ok"] is True
    assert resposta["resultado"]["municipio"] == "Vila Rica"
    assert "cpf" not in resposta["resultado"]
