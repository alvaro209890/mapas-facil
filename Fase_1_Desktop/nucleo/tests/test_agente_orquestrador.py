# G7 — qualidade do loop de orquestração: rodadas, cancelamento, traces, resumo.

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.fake import FakeProvedor, PassoFake, tool_call
from mapasfacil_nucleo.agente.orquestrador import (
    configurar_provedor,
    esquecer_conversa,
    executar_turno,
    mapspec_da_conversa,
    pedir_cancelamento,
)
from mapasfacil_nucleo.agente.provedor import DeltaStream, MensagemLLM
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture
def pasta_chats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    pasta = tmp_path / "chats"
    pasta.mkdir()
    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    conversas_servico.configurar_diretorio(pasta)
    configurar_provedor(None)
    yield pasta
    configurar_provedor(None)
    conversas_servico.configurar_diretorio(None)


@pytest.fixture
def pasta_harmonia(tmp_path: Path) -> Path:
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    return tmp_path


def _nova_conversa(pasta_chats: Path, workspace: str | None = None) -> str:
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=workspace)["conversation_id"]
    repo.fechar()
    return cid


def _mensagens(pasta_chats: Path, cid: str) -> list[dict[str, Any]]:
    repo = RepositorioConversas(pasta_chats)
    try:
        return repo.abrir_conversa(cid, limite=200)["mensagens"]
    finally:
        repo.fechar()


# --------------------------------------------------------------------------- rodadas


def test_doze_rodadas_passam_e_a_decima_terceira_e_ia030(pasta_chats: Path):
    """A fronteira é 12 permitidas / 13ª recusada — nem 11, nem 13."""
    passos = [
        PassoFake(tool_calls=[tool_call("estado_do_projeto", {}, call_id=f"c{i}")])
        for i in range(12)
    ] + [PassoFake(texto="terminei")]
    configurar_provedor(FakeProvedor(passos))
    cid = _nova_conversa(pasta_chats)
    resultado = executar_turno(conversation_id=cid, mensagem="doze rodadas")
    assert resultado["rodadas_tool"] == limites.RODADAS_TOOL_MAX_POR_TURNO
    assert resultado["texto"] == "terminei"


def test_ia030_grava_o_que_ja_tinha_sido_produzido(pasta_chats: Path):
    passos = [
        PassoFake(texto=f"passo {i}", tool_calls=[tool_call("estado_do_projeto", {}, f"c{i}")])
        for i in range(13)
    ]
    configurar_provedor(FakeProvedor(passos))
    cid = _nova_conversa(pasta_chats)
    with pytest.raises(ErroNucleo) as exc:
        executar_turno(conversation_id=cid, mensagem="loop")
    assert exc.value.codigo == limites.CODIGO_LIMITE_RODADAS

    mensagens = _mensagens(pasta_chats, cid)
    assistente = [m for m in mensagens if m["papel"] == "assistente"]
    assert assistente, "o turno estourado não pode sumir do transcript"
    assert "passo 0" in assistente[-1]["conteudo"]
    assert len(assistente[-1]["tool_traces"]) == limites.RODADAS_TOOL_MAX_POR_TURNO


def test_tool_que_erra_conta_rodada(pasta_chats: Path):
    passos = [
        PassoFake(tool_calls=[tool_call("tool_inexistente", {}, call_id=f"c{i}")])
        for i in range(13)
    ]
    configurar_provedor(FakeProvedor(passos))
    cid = _nova_conversa(pasta_chats)
    with pytest.raises(ErroNucleo) as exc:
        executar_turno(conversation_id=cid, mensagem="loop de tool ruim")
    assert exc.value.codigo == limites.CODIGO_LIMITE_RODADAS


def test_texto_de_rodadas_intermediarias_nao_some(pasta_chats: Path, pasta_harmonia: Path):
    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(
                    texto="Vou olhar a pasta primeiro.",
                    tool_calls=[tool_call("listar_arquivos", {}, "c1")],
                ),
                PassoFake(texto="Encontrei 2 shapefiles."),
            ]
        )
    )
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    resultado = executar_turno(conversation_id=cid, mensagem="o que tem na pasta?")
    assert "Vou olhar a pasta primeiro." in resultado["texto"]
    assert "Encontrei 2 shapefiles." in resultado["texto"]


# --------------------------------------------------------------------------- cancelamento


class ProvedorQueCancelaNoMeio:
    """Simula o usuário apertando “parar” no meio do stream."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.cancelado = False

    def enviar_stream(
        self,
        mensagens: list[MensagemLLM],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 8000,
        modelo: str | None = None,
    ) -> Iterator[DeltaStream]:
        del mensagens, tools, max_tokens, modelo
        yield DeltaStream(texto="Estou montando o ma")
        pedir_cancelamento(self.conversation_id)
        yield DeltaStream(texto="pa da Dinâmica 2026…")
        yield DeltaStream(texto=" resto que nunca deveria chegar", finish_reason="stop")

    def cancelar(self) -> None:
        self.cancelado = True


def test_cancelamento_grava_parcial_e_fecha_o_stream(pasta_chats: Path):
    cid = _nova_conversa(pasta_chats)
    provedor = ProvedorQueCancelaNoMeio(cid)
    configurar_provedor(provedor)

    resultado = executar_turno(conversation_id=cid, mensagem="faz a Dinâmica")

    assert resultado["cancelada"] is True
    assert provedor.cancelado is True, "chat.cancelar tem de fechar o HTTP do provedor"
    assert resultado["texto"].startswith("Estou montando o ma")
    assert "nunca deveria chegar" not in resultado["texto"]

    assistente = [m for m in _mensagens(pasta_chats, cid) if m["papel"] == "assistente"]
    assert assistente[-1]["cancelada"] is True
    assert assistente[-1]["conteudo"] == resultado["texto"]


def test_cancelamento_nao_vaza_para_o_proximo_turno(pasta_chats: Path):
    cid = _nova_conversa(pasta_chats)
    configurar_provedor(ProvedorQueCancelaNoMeio(cid))
    executar_turno(conversation_id=cid, mensagem="primeiro")

    configurar_provedor(FakeProvedor([PassoFake(texto="agora vai")]))
    segundo = executar_turno(conversation_id=cid, mensagem="segundo")
    assert segundo["cancelada"] is False
    assert segundo["texto"] == "agora vai"


# --------------------------------------------------------------------------- traces


def test_traces_gravam_args_e_resultado_reais(pasta_chats: Path, pasta_harmonia: Path):
    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(
                    tool_calls=[tool_call("inspecionar_shapefile", {"arquivo": "ATP"}, "c1")]
                ),
                PassoFake(texto="pronto"),
            ]
        )
    )
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    executar_turno(conversation_id=cid, mensagem="inspeciona o ATP")

    assistente = [m for m in _mensagens(pasta_chats, cid) if m["papel"] == "assistente"]
    traces = assistente[-1]["tool_traces"]
    assert len(traces) == 1
    assert traces[0]["tool"] == "inspecionar_shapefile"
    assert "ATP" in (traces[0]["args_resumo"] or "")
    assert traces[0]["resultado_resumo"] not in (None, "", "ok")
    assert traces[0]["ok"] is True
    assert traces[0]["ms"] is not None


def test_trace_de_tool_que_falha_guarda_o_codigo(pasta_chats: Path):
    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(tool_calls=[tool_call("tool_fantasma", {}, "c1")]),
                PassoFake(texto="essa tool não existe"),
            ]
        )
    )
    cid = _nova_conversa(pasta_chats)
    executar_turno(conversation_id=cid, mensagem="chama uma tool que não existe")
    traces = [m for m in _mensagens(pasta_chats, cid) if m["papel"] == "assistente"][-1][
        "tool_traces"
    ]
    assert traces[0]["ok"] is False
    assert traces[0]["erro_codigo"] == limites.CODIGO_TOOL_INEXISTENTE


# --------------------------------------------------------------------------- resumo


def test_compact_summary_so_cobre_o_que_esta_fora_da_janela_verbatim(pasta_chats: Path):
    """Nem a cada turno, nem cobrindo o que já vai verbatim no payload."""
    cid = _nova_conversa(pasta_chats)
    repo = RepositorioConversas(pasta_chats)
    marcos: list[tuple[int, int, str | None]] = []
    try:
        for i in range(14):
            configurar_provedor(FakeProvedor([PassoFake(texto=f"resposta {i}")]))
            executar_turno(conversation_id=cid, mensagem=f"pergunta {i}")
            ctx = repo.contexto_para_turno(cid)
            marcos.append((ctx.total_mensagens, ctx.compact_ate_seq, ctx.compact_summary))
    finally:
        repo.fechar()

    cauda = limites.TURNOS_VERBATIM * 2
    # enquanto tudo cabe verbatim, não existe resumo — resumir seria gasto puro
    assert all(resumo is None for total, _, resumo in marcos if total <= cauda)

    com_resumo = [(total, ate_seq) for total, ate_seq, resumo in marcos if resumo]
    assert com_resumo, "o compact_summary nunca foi gerado"
    # o resumo cobre exatamente o histórico fora da janela verbatim
    for total, ate_seq in com_resumo:
        assert ate_seq <= total - cauda

    # e não é regenerado a cada turno: o passo é de COMPACT_SUMMARY_REGENERAR_CADA
    seqs = sorted({ate_seq for _, ate_seq in com_resumo})
    for anterior, seguinte in zip(seqs, seqs[1:]):
        assert seguinte - anterior >= limites.COMPACT_SUMMARY_REGENERAR_CADA


# --------------------------------------------------------------------------- mapspec


def test_mapspec_sobrevive_entre_turnos_e_e_editavel(pasta_chats: Path, pasta_harmonia: Path):
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    esquecer_conversa(cid)
    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(
                    tool_calls=[
                        tool_call(
                            "usar_modelo_da_galeria", {"modelo_id": "dinamica_2026_retrato"}, "c1"
                        )
                    ]
                ),
                PassoFake(texto="montei pelo modelo"),
            ]
        )
    )
    primeiro = executar_turno(conversation_id=cid, mensagem="faz a Dinâmica 2026")
    assert primeiro["mapspec_versao"] == 1

    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(
                    tool_calls=[
                        tool_call("alternar_elemento", {"elemento": "tabela", "ligado": False}, "c2")
                    ]
                ),
                PassoFake(texto="tabela desligada"),
            ]
        )
    )
    segundo = executar_turno(conversation_id=cid, mensagem="tira a tabela")
    assert segundo["mapspec_versao"] == 2
    assert segundo["mapspec"]["parent_id"] == primeiro["mapspec"]["id"]
    assert segundo["mapspec"]["elementos_layout"]["tabela"] is False
    assert mapspec_da_conversa(cid)["versao"] == 2
    esquecer_conversa(cid)
