# Gate AUTH-030 e sessao.* (F1-14 / M5).

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo import sessao
from mapasfacil_nucleo.__main__ import processar_linha
from mapasfacil_nucleo.contas import servico as contas_servico
from mapasfacil_nucleo.protocolo import envelope_req
from mapasfacil_nucleo.workspace import servico as workspace_servico


@pytest.fixture
def isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pasta = tmp_path / "contas"
    pasta.mkdir()
    monkeypatch.setenv("MAPASFACIL_CONTAS_DIR", str(pasta))
    contas_servico.configurar_diretorio(pasta)
    sessao.resetar()
    yield tmp_path
    sessao.resetar()
    contas_servico.configurar_diretorio(None)


def _ndjson(metodo: str, params: dict | None = None) -> dict:
    return json.loads(processar_linha(json.dumps(envelope_req(metodo, params or {}))))


def test_mapa_gerar_sem_sessao_auth_030(isolado: Path, mapspec_canonico: dict):
    projeto = isolado / "proj"
    for nome in ("Mapas", "MXD", "SHP", "_extraido", "dados"):
        (projeto / nome).mkdir(parents=True)
    workspace_servico.abrir(str(projeto))
    sessao.resetar()
    assert not sessao.conectada()

    r = _ndjson("mapa.gerar", {"mapspec": mapspec_canonico})
    assert r["ok"] is False
    assert r["erro"]["codigo"] == "AUTH-030"


def test_metodos_sem_gate(isolado: Path):
    sessao.resetar()
    r = _ndjson("doctor.rodar", {})
    assert r["ok"] is True
    r2 = _ndjson("workspace.abrir", {"caminho": str(isolado)})
    # Pode falhar por NU-010/estrutura, mas NÃO por AUTH-030
    if not r2["ok"]:
        assert r2["erro"]["codigo"] != "AUTH-030"


def test_sessao_definir_libera_gate(isolado: Path):
    sessao.resetar()
    r = _ndjson("sessao.definir", {"estado": "conectado", "conta_id": "x"})
    assert r["ok"] is True
    assert r["resultado"]["estado"] == "conectado"
    assert sessao.conectada()
    estado = _ndjson("sessao.estado", {})
    assert estado["resultado"]["conta_id"] == "x"
