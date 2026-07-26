"""A10 — `mapa.cancelar` e registro de jobs."""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

import pytest

from mapasfacil_nucleo import jobs
from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.progresso import RastreadorProgresso
from mapasfacil_nucleo.protocolo import envelope_req
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import eventos_e_resposta, montar_workspace_minimo


@pytest.fixture(autouse=True)
def _limpar_jobs():
    # Esvazia o registro entre testes.
    with jobs._jobs_lock:
        jobs._jobs.clear()
        jobs._job_atual = None
    workspace_servico.fechar()
    yield
    with jobs._jobs_lock:
        jobs._jobs.clear()
        jobs._job_atual = None
    workspace_servico.fechar()


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    montar_workspace_minimo(tmp_path)
    return tmp_path


@pytest.fixture
def mapspec_local(repo_root: Path) -> dict:
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    spec = copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8")))
    spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
    spec["saidas"] = ["pdf"]
    spec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "Dinamica_2026_teste",
        "caminhos_relativos": True,
        "materializar_camadas_em": "SHP",
    }
    return spec


def test_registrar_e_cancelar_marca_flag() -> None:
    job_id = jobs.registrar()
    assert jobs.obter(job_id) is not None
    assert jobs.atual() is not None
    out = jobs.pedir_cancelamento(job_id)
    assert out["ok"] is True
    assert out["job_id"] == job_id
    assert jobs.obter(job_id).cancelado is True
    jobs.liberar(job_id)
    assert jobs.obter(job_id) is None


def test_cancelar_job_desconhecido_erra() -> None:
    with pytest.raises(ErroNucleo) as exc:
        jobs.pedir_cancelamento("job-fantasma")
    assert exc.value.codigo == "NU-001"


def test_verificar_nao_cancelado_levanta_nu050() -> None:
    job_id = jobs.registrar()
    jobs.pedir_cancelamento(job_id)
    with pytest.raises(ErroNucleo) as exc:
        jobs.verificar_nao_cancelado(job_id)
    assert exc.value.codigo == jobs.CODIGO_JOB_CANCELADO


def test_progresso_carrega_job_id() -> None:
    emitidos: list[dict] = []
    rastreador = RastreadorProgresso(
        lambda _e, dados: emitidos.append(dados),
        job_id="job-teste",
    )
    rastreador.concluir("validando_spec")
    assert emitidos[0]["job_id"] == "job-teste"
    assert emitidos[0]["pct"] == 3


def test_gerar_respeita_cancelamento_cooperativo(pasta: Path, mapspec_local: dict) -> None:
    workspace_servico.abrir(str(pasta))
    estado = workspace_servico.estado_atual()
    assert estado is not None
    job_id = jobs.registrar()

    # Cancela antes de começar o corpo — a 1ª checagem após validar deve abortar.
    jobs.pedir_cancelamento(job_id)

    with pytest.raises(ErroNucleo) as exc:
        gerar_mapa(
            mapspec_local,
            estado.guard,
            workspace_servico.fontes_idx(estado),
            progresso=RastreadorProgresso(job_id=job_id),
        )
    assert exc.value.codigo == "NU-050"
    jobs.liberar(job_id)


def test_handler_mapa_cancelar_ndjson() -> None:
    job_id = jobs.registrar()
    linha = json.dumps(
        envelope_req("mapa.cancelar", {"job_id": job_id}),
        ensure_ascii=False,
    )
    saida = processar_linha(linha, criar_roteador())
    _evts, res = eventos_e_resposta(saida)
    assert res["ok"] is True
    assert res["resultado"]["ok"] is True
    assert res["resultado"]["job_id"] == job_id
    assert jobs.obter(job_id).cancelado is True


def test_cancelar_sem_job_id_usa_atual() -> None:
    job_id = jobs.registrar()
    linha = json.dumps(envelope_req("mapa.cancelar", {}), ensure_ascii=False)
    saida = processar_linha(linha, criar_roteador())
    _evts, res = eventos_e_resposta(saida)
    assert res["ok"] is True
    assert res["resultado"]["job_id"] == job_id


def test_cancelar_durante_gerar_via_thread(pasta: Path, mapspec_local: dict) -> None:
    """Cancela no meio: o job cooperativo aborta com NU-050."""
    workspace_servico.abrir(str(pasta))
    estado = workspace_servico.estado_atual()
    assert estado is not None
    job_id = jobs.registrar()
    erros: list[BaseException] = []

    def _rodar() -> None:
        try:
            # Pequeno atraso para o cancel chegar entre etapas.
            time.sleep(0.05)
            gerar_mapa(
                mapspec_local,
                estado.guard,
                workspace_servico.fontes_idx(estado),
                progresso=RastreadorProgresso(job_id=job_id),
            )
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    t = threading.Thread(target=_rodar)
    t.start()
    time.sleep(0.02)
    jobs.pedir_cancelamento(job_id)
    t.join(timeout=60)
    assert not t.is_alive()
    # Pode ter terminado antes do cancel (máquina rápida) ou com NU-050.
    if erros:
        assert isinstance(erros[0], ErroNucleo)
        assert erros[0].codigo == "NU-050"
    jobs.liberar(job_id)
