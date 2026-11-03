"""W5-01/W5-03 — log de eventos com `seq`, replay e vocabulário."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mapasfacil_servidor.eventos import log as log_mod
from mapasfacil_servidor.eventos import vocabulario

NUCLEO_PROTOCOLO = (
    Path(__file__).resolve().parents[3]
    / "Fase_1_Desktop"
    / "nucleo"
    / "mapasfacil_nucleo"
    / "protocolo.py"
)


@pytest.fixture
def log(tmp_path):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    return log_mod.LogEventos(raiz)


# --- vocabulário ----------------------------------------------------------


def test_vocabulario_fechado():
    assert vocabulario.valido("job.progresso")
    assert vocabulario.valido("versao.criada")
    assert not vocabulario.valido("job.inventado")
    with pytest.raises(ValueError):
        vocabulario.exigir("evento.que.nao.existe")


def test_origens():
    assert vocabulario.ORIGENS == {"nucleo", "servidor"}


def test_eventos_do_nucleo_batem_com_o_protocolo_real():
    if not NUCLEO_PROTOCOLO.exists():  # pragma: no cover - repo incompleto
        pytest.skip("protocolo do núcleo não encontrado")
    texto = NUCLEO_PROTOCOLO.read_text(encoding="utf-8")
    bloco = re.search(r"EVENTOS: frozenset\[str\] = frozenset\((.*?)\n\)", texto, re.S)
    assert bloco, "não achei o bloco EVENTOS no protocolo do núcleo"
    nomes = set(re.findall(r'"([a-z.]+)"', bloco.group(1)))
    assert nomes <= vocabulario.EVENTOS_NUCLEO, (
        "evento no núcleo que o servidor não conhece: "
        + ", ".join(sorted(nomes - vocabulario.EVENTOS_NUCLEO))
    )


# --- log ------------------------------------------------------------------


def test_seq_comeca_em_1_e_cresce(log):
    primeiro = log.registrar(origem="servidor", evento="projeto.estado", dados={"estado": "pronto"})
    segundo = log.registrar(origem="nucleo", evento="job.progresso", dados={"pct": 10})
    assert primeiro["seq"] == 1
    assert segundo["seq"] == 2
    assert log.ultimo_seq() == 2


def test_seq_continua_depois_de_reabrir(tmp_path):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    log1 = log_mod.LogEventos(raiz)
    log1.registrar(origem="servidor", evento="projeto.estado")
    log1.registrar(origem="servidor", evento="projeto.estado")

    log2 = log_mod.LogEventos(raiz)  # simula reinício do servidor
    assert log2.ultimo_seq() == 2
    assert log2.registrar(origem="servidor", evento="projeto.estado")["seq"] == 3


def test_replay_desde_250_de_500(log):
    for i in range(500):
        log.registrar(origem="nucleo", evento="job.log", dados={"i": i})
    eventos = log.ler_desde(250)
    assert len(eventos) == 250
    assert eventos[0]["seq"] == 251
    assert eventos[-1]["seq"] == 500


def test_replay_usa_indice_e_nao_duplica(log):
    for i in range(2500):
        log.registrar(origem="nucleo", evento="job.log", dados={"i": i})
    assert log_mod.caminho_indice(log.raiz_projeto).is_file()
    eventos = log.ler_desde(2400)
    assert eventos[0]["seq"] == 2401
    assert len(eventos) == 100
    # reconexão com Last-Event-ID = último recebido não repete nada
    ultimo = eventos[-1]["seq"]
    assert log.ler_desde(ultimo) == []


def test_evento_inexistente_nao_quebra_leitura(log):
    log.registrar(origem="servidor", evento="projeto.estado")
    caminho = log_mod.caminho_log(log.raiz_projeto)
    with open(caminho, "a", encoding="utf-8") as arquivo:
        arquivo.write('{"seq": 99, "lixo"')  # linha truncada por queda
    eventos = log.ler_desde(0)
    assert len(eventos) == 1


def test_caminho_absoluto_removido_do_evento(log):
    envelope = log.registrar(
        origem="nucleo",
        evento="job.log",
        dados={
            "texto": "abriu /home/server/dados/x.shp",
            "windows": r"C:\GIS\algo.mxd",
            "ok": "Mapas/v001/mapa.pdf",
            "lista": ["/media/server/HD Backup/x"],
        },
    )
    assert envelope["dados"]["texto"] == "abriu <caminho removido>"
    assert envelope["dados"]["windows"] == "<caminho removido>"
    assert envelope["dados"]["ok"] == "Mapas/v001/mapa.pdf"
    # Caminho com espaço é mascarado até o primeiro espaço — o prefixo absoluto
    # (que é o que identifica a máquina) nunca vaza.
    assert envelope["dados"]["lista"][0].startswith("<caminho removido>")
    assert "/media/" not in envelope["dados"]["lista"][0]


def test_compactacao_de_reabertura(log):
    """`desde=0` com 3 jobs: um progresso final por job, sem `chat.delta`."""
    for job in ("j1", "j2", "j3"):
        for pct in (10, 50, 100):
            log.registrar(
                origem="nucleo", evento="job.progresso", dados={"pct": pct}, job_id=job
            )
        log.registrar(
            origem="nucleo", evento="chat.delta", dados={"texto": "oi"}, job_id=job
        )
        log.registrar(
            origem="nucleo", evento="camada.renderizada", dados={"camada_id": "avn"}, job_id=job
        )
        log.registrar(origem="servidor", evento="nucleo.res", dados={"ok": True}, job_id=job)

    todos = log.ler_desde(0)
    compactado = log.compactar(todos)
    nomes = [e["evento"] for e in compactado]
    assert nomes.count("job.progresso") == 3
    assert "chat.delta" not in nomes
    assert nomes.count("camada.renderizada") == 3
    assert all(e["dados"].get("pct") == 100 for e in compactado if e["evento"] == "job.progresso")


def test_origem_invalida_recusada(log):
    with pytest.raises(ValueError):
        log.registrar(origem="hacker", evento="job.log")


def test_evento_fora_do_vocabulario_recusado(log):
    with pytest.raises(ValueError):
        log.registrar(origem="servidor", evento="evento.inventado")


def test_arquivo_e_ndjson_legivel(log):
    log.registrar(origem="servidor", evento="projeto.estado", dados={"estado": "pronto"})
    caminho = log_mod.caminho_log(log.raiz_projeto)
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1
    dados = json.loads(linhas[0])
    assert dados["evento"] == "projeto.estado"
    assert dados["ts"].endswith("Z")
