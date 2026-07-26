# H6/A6 — evento `mapspec.atualizado` (F1-01 §Eventos, F1-16 §A6 troca de versão).
#
# Critério: toda tool que cria/edita o MapSpec do turno emite o evento com
# `{id, versao, diff}`; sem `Emissor` (chamada de biblioteca/teste sem turno) é
# no-op — não quebra quem não passa emissor.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest

from mapasfacil_nucleo.agente.contexto import assert_sem_vazamento
from mapasfacil_nucleo.agente.fake import FakeProvedor, PassoFake, tool_call
from mapasfacil_nucleo.agente.orquestrador import configurar_provedor, esquecer_conversa, executar_turno
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.protocolo import Emissor, envelope_req
from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
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
    yield tmp_path
    workspace_servico.fechar()


def _nova_conversa(pasta_chats: Path, workspace: str | None = None) -> str:
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=workspace)["conversation_id"]
    repo.fechar()
    return cid


def _emissor_coletor() -> tuple[Emissor, list[dict[str, Any]]]:
    eventos: list[dict[str, Any]] = []
    return Emissor("teste", sink=eventos.append), eventos


def _so_mapspec_atualizado(eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e["dados"] for e in eventos if e["evento"] == "mapspec.atualizado"]


def test_usar_modelo_da_galeria_emite_mapspec_atualizado(
    pasta_chats: Path, pasta_harmonia: Path
):
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    esquecer_conversa(cid)
    emissor, eventos = _emissor_coletor()
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
                PassoFake(texto="montei"),
            ]
        )
    )
    resultado = executar_turno(conversation_id=cid, mensagem="monta o modelo", emissor=emissor)

    atualizacoes = _so_mapspec_atualizado(eventos)
    assert len(atualizacoes) == 1
    dados = atualizacoes[0]
    assert dados["id"] == resultado["mapspec"]["id"]
    assert dados["versao"] == 1
    assert dados["diff"]["operacoes"]  # v1: tudo "adicionar" contra {}
    assert dados["diff"]["resumo"]  # linhas em português, não só a estrutura crua


def test_editar_camada_emite_mapspec_atualizado_com_diff_da_alteracao(
    pasta_chats: Path, pasta_harmonia: Path
):
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    esquecer_conversa(cid)
    emissor, eventos = _emissor_coletor()

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
                PassoFake(texto="montei"),
            ]
        )
    )
    primeiro = executar_turno(conversation_id=cid, mensagem="monta", emissor=emissor)

    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(
                    tool_calls=[
                        tool_call("alternar_elemento", {"elemento": "tabela", "ligado": False}, "c2")
                    ]
                ),
                PassoFake(texto="tirei a tabela"),
            ]
        )
    )
    segundo = executar_turno(conversation_id=cid, mensagem="tira a tabela", emissor=emissor)

    atualizacoes = _so_mapspec_atualizado(eventos)
    assert len(atualizacoes) == 2  # uma por turno que mudou o MapSpec
    ultima = atualizacoes[-1]
    assert ultima["id"] == segundo["mapspec"]["id"]
    assert ultima["id"] != primeiro["mapspec"]["id"]
    assert ultima["versao"] == 2

    caminhos = {op["caminho"] for op in ultima["diff"]["operacoes"] if op["caminho"] != "id"}
    assert "elementos_layout/tabela" in caminhos
    assert any("tabela" in linha for linha in ultima["diff"]["resumo"])


def test_criar_mapa_emite_mapspec_atualizado(pasta_chats: Path, pasta_harmonia: Path):
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    esquecer_conversa(cid)
    emissor, eventos = _emissor_coletor()
    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(
                    tool_calls=[tool_call("criar_mapa", {"template": "dinamica_retrato"}, "c1")]
                ),
                PassoFake(texto="criei do zero"),
            ]
        )
    )
    executar_turno(conversation_id=cid, mensagem="cria do zero", emissor=emissor)
    atualizacoes = _so_mapspec_atualizado(eventos)
    assert len(atualizacoes) == 1
    assert atualizacoes[0]["versao"] == 1


def test_sem_emissor_nao_quebra(pasta_chats: Path, pasta_harmonia: Path):
    """`executar_turno` sem `emissor` (ex.: modo determinístico/testes) não falha."""
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
                PassoFake(texto="ok"),
            ]
        )
    )
    resultado = executar_turno(conversation_id=cid, mensagem="monta", emissor=None)
    assert resultado["mapspec_versao"] == 1


def test_tool_que_nao_muda_mapspec_nao_emite(pasta_chats: Path, pasta_harmonia: Path):
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    esquecer_conversa(cid)
    emissor, eventos = _emissor_coletor()
    configurar_provedor(
        FakeProvedor(
            [
                PassoFake(tool_calls=[tool_call("estado_do_projeto", {}, "c1")]),
                PassoFake(texto="tudo certo"),
            ]
        )
    )
    executar_turno(conversation_id=cid, mensagem="como está o projeto?", emissor=emissor)
    assert _so_mapspec_atualizado(eventos) == []


def test_payload_do_evento_sem_wkt_cpf_caminho_chave(pasta_chats: Path, pasta_harmonia: Path):
    cid = _nova_conversa(pasta_chats, workspace=str(pasta_harmonia))
    esquecer_conversa(cid)
    emissor, eventos = _emissor_coletor()
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
                PassoFake(texto="montei"),
            ]
        )
    )
    executar_turno(conversation_id=cid, mensagem="monta", emissor=emissor)
    atualizacoes = _so_mapspec_atualizado(eventos)
    assert atualizacoes
    payload = json.dumps(atualizacoes, ensure_ascii=False)
    assert_sem_vazamento(payload)


def test_ndjson_chat_enviar_emite_mapspec_atualizado_no_canal_real(
    pasta_chats: Path, pasta_harmonia: Path
):
    """Round-trip completo: `chat.enviar` NDJSON → linha `evt` de `mapspec.atualizado`."""
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
                PassoFake(texto="montei pelo NDJSON"),
            ]
        )
    )
    linha = json.dumps(
        envelope_req("chat.enviar", {"conversation_id": cid, "mensagem": "monta"}),
        ensure_ascii=False,
    )
    saida = processar_linha(linha, criar_roteador())
    mensagens = [json.loads(l) for l in saida.splitlines() if l.strip()]
    eventos_mapspec = [
        m for m in mensagens if m.get("tipo") == "evt" and m.get("evento") == "mapspec.atualizado"
    ]
    assert len(eventos_mapspec) == 1
    assert eventos_mapspec[0]["dados"]["versao"] == 1
    assert "id" in eventos_mapspec[0]["dados"]
    assert "diff" in eventos_mapspec[0]["dados"]
