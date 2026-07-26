# F1-01 §Eventos — `job.log` e `aviso`, os dois últimos do vocabulário que ainda
# não tinham emissor. Depois deste arquivo, `protocolo.EVENTOS` está 8/8 emitido.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.progresso import (
    MAX_LINHAS_LOG,
    MAX_TAMANHO_LINHA,
    RastreadorProgresso,
)
from mapasfacil_nucleo.protocolo import EVENTOS, envelope_req
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import (
    escrever_recibo_car_pdf,
    escrever_shapefile_quadrado_utm,
    linhas_ndjson,
)


def _coletor() -> tuple[list[tuple[str, dict[str, Any]]], RastreadorProgresso]:
    eventos: list[tuple[str, dict[str, Any]]] = []
    return eventos, RastreadorProgresso(
        lambda evento, dados: eventos.append((evento, dados)), job_id="job-teste"
    )


# --------------------------------------------------------------------------- unidade


def test_log_emite_job_log_com_job_id() -> None:
    eventos, prog = _coletor()
    prog.log("materializou 4 camadas")
    assert eventos == [("job.log", {"linha": "materializou 4 camadas", "job_id": "job-teste"})]


def test_log_vazio_nao_emite() -> None:
    eventos, prog = _coletor()
    assert prog.log("   ") is None
    assert eventos == []


def test_log_trunca_linha_muito_longa() -> None:
    eventos, prog = _coletor()
    prog.log("x" * (MAX_TAMANHO_LINHA + 500))
    assert len(eventos[0][1]["linha"]) == MAX_TAMANHO_LINHA


def test_log_para_de_emitir_apos_o_teto_avisando_que_cortou() -> None:
    """Pasta patológica não pode encher a memória do renderer — mas o corte é dito."""
    eventos, prog = _coletor()
    for i in range(MAX_LINHAS_LOG + 50):
        prog.log(f"linha {i}")
    linhas = [d["linha"] for _e, d in eventos]
    assert len(linhas) == MAX_LINHAS_LOG + 1
    assert "truncado" in linhas[-1]


def test_aviso_emite_codigo_e_mensagem() -> None:
    eventos, prog = _coletor()
    prog.aviso("NU-120", "Camada 'x' sem feições após o recorte.")
    evento, dados = eventos[0]
    assert evento == "aviso"
    assert dados["codigo"] == "NU-120"
    assert dados["mensagem"].startswith("Camada 'x'")


def test_sem_emissor_log_e_aviso_sao_noop() -> None:
    """`gerar_mapa` como biblioteca (CLI/teste) não paga por evento que ninguém ouve."""
    prog = RastreadorProgresso()
    assert prog.log("nada")["linha"] == "nada"
    assert prog.aviso("NU-120", "nada")["codigo"] == "NU-120"


def test_vocabulario_de_eventos_cobre_os_dois() -> None:
    assert "job.log" in EVENTOS
    assert "aviso" in EVENTOS


# --------------------------------------------------------------------------- integração


@pytest.fixture
def pasta_harmonia(tmp_path: Path):
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    (tmp_path / "Mapas").mkdir(exist_ok=True)
    workspace_servico.abrir(str(tmp_path))
    yield tmp_path
    workspace_servico.fechar()


def _gerar_ndjson(pasta: Path) -> list[dict[str, Any]]:
    from mapasfacil_nucleo.galeria.montar import montar_mapspec

    mapspec = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta))["mapspec"]
    linha = json.dumps(
        envelope_req("mapa.gerar", {"mapspec": mapspec}), ensure_ascii=False
    )
    return linhas_ndjson(processar_linha(linha, criar_roteador()))


def test_mapa_gerar_emite_job_log_no_canal_ndjson(pasta_harmonia: Path) -> None:
    mensagens = _gerar_ndjson(pasta_harmonia)
    logs = [m for m in mensagens if m.get("evento") == "job.log"]
    assert logs, "mapa.gerar tem de emitir job.log"
    assert any("job iniciado" in m["dados"]["linha"] for m in logs)
    assert any("job concluído" in m["dados"]["linha"] for m in logs)
    for m in logs:
        assert isinstance(m["dados"]["linha"], str)


def test_job_log_nunca_carrega_caminho_absoluto(pasta_harmonia: Path) -> None:
    """Fronteira 1 de F1-01: log é para o renderer — nada de estrutura de disco."""
    mensagens = _gerar_ndjson(pasta_harmonia)
    for m in mensagens:
        if m.get("evento") != "job.log":
            continue
        linha = m["dados"]["linha"]
        assert str(pasta_harmonia) not in linha
        assert not linha.startswith("/")


def test_aviso_sai_como_evento_e_tambem_no_relatorio(pasta_harmonia: Path) -> None:
    """O mesmo aviso tem de aparecer nos dois lugares — nem só um, nem só o outro."""
    mensagens = _gerar_ndjson(pasta_harmonia)
    avisos_evt = [m for m in mensagens if m.get("evento") == "aviso"]
    resposta = mensagens[-1]
    assert resposta["tipo"] == "res" and resposta["ok"] is True
    avisos_relatorio = resposta["resultado"]["avisos"]

    # Este workspace gera ao menos um aviso (template `parcial`, sem offsets).
    if avisos_relatorio:
        assert avisos_evt, "aviso no relatório mas nenhum evento emitido"
        mensagens_evt = {m["dados"]["mensagem"] for m in avisos_evt}
        assert mensagens_evt == set(avisos_relatorio)
        for m in avisos_evt:
            assert m["dados"]["codigo"].startswith("NU-")


def test_escala_auto_do_modelo_da_galeria_nao_derruba_o_job(pasta_harmonia: Path) -> None:
    """Regressão: `escala: "auto"` (default dos modelos) virava ValueError sem código.

    O modelo `dinamica_2026_retrato` pede `.mxd` e traz `escala: "auto"`; o job
    fazia `float("auto")` e morria com `NU-000` — justamente o caminho de
    paridade galeria↔chat.
    """
    mensagens = _gerar_ndjson(pasta_harmonia)
    resposta = mensagens[-1]
    assert resposta["ok"] is True, resposta.get("erro")
    assert resposta["resultado"]["mxd"]


def test_escala_numerica_continua_virando_patch() -> None:
    from mapasfacil_nucleo.motores.gerar import _escala_numerica

    assert _escala_numerica(60000) == 60000.0
    assert _escala_numerica("60000") == 60000.0
    assert _escala_numerica("auto") is None
    assert _escala_numerica("AUTO") is None
    assert _escala_numerica(None) is None
    assert _escala_numerica("nada disso") is None
