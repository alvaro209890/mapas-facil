"""W5-02 — SSE: replay sem buraco, sem duplicata, com heartbeat."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mapasfacil_servidor.eventos import log as log_mod
from mapasfacil_servidor.eventos import sse


@pytest.fixture
def raiz(tmp_path):
    caminho = tmp_path / "projeto"
    caminho.mkdir()
    return caminho


def extrair_envelopes(blocos: list[str]) -> list[dict]:
    """Lê `data:` dos blocos SSE (ignora heartbeat)."""
    eventos = []
    for bloco in blocos:
        for linha in bloco.splitlines():
            if linha.startswith("data: "):
                eventos.append(json.loads(linha[6:]))
    return eventos


async def juntar(gerador, quantidade: int, timeout: float = 3.0) -> list[str]:
    blocos: list[str] = []
    try:
        while len(blocos) < quantidade:
            blocos.append(await asyncio.wait_for(gerador.__anext__(), timeout))
    finally:
        await gerador.aclose()
    return blocos


def test_formato_do_bloco_sse():
    bloco = sse.formatar_sse({"seq": 7, "evento": "job.log", "dados": {"a": "á"}})
    assert bloco.startswith("id: 7\nevent: mf\ndata: ")
    assert bloco.endswith("\n\n")
    assert "á" in bloco  # sem escape ascii — o cliente lê UTF-8
    assert '"seq":7' in bloco


def test_cabecalhos_sse():
    cabecalhos = sse.cabecalhos_sse()
    assert cabecalhos["Cache-Control"] == "no-cache"
    assert cabecalhos["X-Accel-Buffering"] == "no"
    assert cabecalhos["Content-Type"].startswith("text/event-stream")


def test_replay_de_500_com_desde_250(raiz):
    log = log_mod.LogEventos(raiz)
    for i in range(500):
        log.registrar(origem="nucleo", evento="job.log", dados={"i": i})

    async def cenario():
        hub = sse.Hub()
        gerador = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=250)
        blocos = await juntar(gerador, 250)
        return blocos

    envelopes = extrair_envelopes(asyncio.run(cenario()))
    assert [e["seq"] for e in envelopes] == list(range(251, 501))


def test_replay_e_ao_vivo_sem_duplicata(raiz):
    log = log_mod.LogEventos(raiz)
    for i in range(3):
        log.registrar(origem="nucleo", evento="job.log", dados={"i": i})

    async def cenario():
        hub = sse.Hub()
        gerador = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=1)
        primeiro = await asyncio.wait_for(gerador.__anext__(), 2)  # replay do seq 2
        segundo_do_replay = await asyncio.wait_for(gerador.__anext__(), 2)  # replay do seq 3
        assert extrair_envelopes([segundo_do_replay])[0]["seq"] == 3
        # evento ao vivo com seq repetido (já veio no replay) e um novo
        hub.publicar("p1", {"seq": 2, "evento": "job.log", "dados": {"dup": True}})
        hub.publicar("p1", {"seq": 4, "evento": "job.log", "dados": {"novo": True}})
        segundo = await asyncio.wait_for(gerador.__anext__(), 2)
        await gerador.aclose()
        return primeiro, segundo

    primeiro, segundo = asyncio.run(cenario())
    assert extrair_envelopes([primeiro])[0]["seq"] == 2
    # o seq 3 (do log) também vem no replay? não: `desde=1` já entregou 2 e 3
    assert extrair_envelopes([segundo])[0]["seq"] == 4


def test_replay_entrega_tudo_antes_do_ao_vivo(raiz):
    log = log_mod.LogEventos(raiz)
    for i in range(5):
        log.registrar(origem="nucleo", evento="job.log", dados={"i": i})

    async def cenario():
        hub = sse.Hub()
        gerador = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=0)
        blocos = await juntar(gerador, 5)
        return blocos

    envelopes = extrair_envelopes(asyncio.run(cenario()))
    assert [e["seq"] for e in envelopes] == [1, 2, 3, 4, 5]


def test_heartbeat_chega_quando_nao_ha_evento(raiz):
    async def cenario():
        hub = sse.Hub()
        gerador = sse.fluxo(
            raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=0, heartbeat_s=0.05
        )
        bloco = await asyncio.wait_for(gerador.__anext__(), 2)
        await gerador.aclose()
        return bloco

    bloco = asyncio.run(cenario())
    assert bloco == ": ♥\n\n"


def test_desconexao_limpa_a_assinatura(raiz):
    async def cenario():
        hub = sse.Hub()
        gerador = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=0)
        await gerador.__anext__()  # heartbeat
        antes = hub.assinantes("p1")
        await gerador.aclose()
        return antes, hub.assinantes("p1")

    antes, depois = asyncio.run(cenario())
    assert antes == 1
    assert depois == 0


def test_compactacao_quando_desde_zero_e_arquivo_grande(raiz):
    log = log_mod.LogEventos(raiz)
    for job in ("j1", "j2"):
        for pct in range(1, 201):
            log.registrar(
                origem="nucleo", evento="job.progresso", dados={"pct": pct}, job_id=job
            )
        # `nucleo.res` marca o job como terminado — é o que permite compactar
        log.registrar(
            origem="servidor", evento="nucleo.res", dados={"ok": True}, job_id=job
        )

    async def cenario():
        hub = sse.Hub()
        gerador = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=0)
        blocos = []
        try:
            while True:
                blocos.append(await asyncio.wait_for(gerador.__anext__(), 0.5))
        except (asyncio.TimeoutError, StopAsyncIteration):
            pass
        finally:
            await gerador.aclose()
        return blocos

    envelopes = extrair_envelopes(asyncio.run(cenario()))
    progressos = [e for e in envelopes if e["evento"] == "job.progresso"]
    assert len(progressos) == 2, f"compactação deveria deixar 1 progresso por job: {len(progressos)}"
    assert all(e["dados"]["pct"] == 200 for e in progressos)
    assert len([e for e in envelopes if e["evento"] == "nucleo.res"]) == 2


def test_duas_abas_recebem_o_mesmo_evento(raiz):
    async def cenario():
        hub = sse.Hub()
        g1 = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=0, heartbeat_s=5)
        g2 = sse.fluxo(raiz_projeto=raiz, projeto_id="p1", hub=hub, desde=0, heartbeat_s=5)
        t1 = asyncio.create_task(g1.__anext__())
        t2 = asyncio.create_task(g2.__anext__())
        await asyncio.sleep(0.01)
        hub.publicar("p1", {"seq": 1, "evento": "aviso", "dados": {}})
        b1, b2 = await asyncio.gather(t1, t2)
        await g1.aclose()
        await g2.aclose()
        return b1, b2

    b1, b2 = asyncio.run(cenario())
    assert extrair_envelopes([b1])[0]["seq"] == 1
    assert extrair_envelopes([b2])[0]["seq"] == 1
