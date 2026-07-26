# G8 — cassetes VCR do agente (sem rede / sem chave).

from __future__ import annotations

from pathlib import Path

import pytest

from mapasfacil_nucleo.agente.deepseek import DeepSeekProvedor
from mapasfacil_nucleo.agente.orquestrador import (
    configurar_provedor,
    executar_turno,
    mapspec_da_conversa,
    esquecer_conversa,
)
from mapasfacil_nucleo.agente.provedor import MensagemLLM
from mapasfacil_nucleo.agente.vcr import opener_de_cassete, provedor_de_cassete
from mapasfacil_nucleo.agente import mapspec_store
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture
def pasta_chats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pasta = tmp_path / "chats"
    pasta.mkdir()
    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta))
    from mapasfacil_nucleo.conversas import servico as conversas_servico

    conversas_servico.configurar_diretorio(pasta)
    yield pasta
    conversas_servico.configurar_diretorio(None)
    configurar_provedor(None)


@pytest.fixture
def pasta_harmonia(tmp_path: Path):
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    return tmp_path


def test_cassete_fake_orquestra_galeria(pasta_chats: Path, pasta_harmonia: Path):
    workspace_servico.abrir(str(pasta_harmonia))
    configurar_provedor(provedor_de_cassete("galeria_dinamica"))
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=str(pasta_harmonia))["conversation_id"]
    repo.fechar()

    resultado = executar_turno(conversation_id=cid, mensagem="faz a Dinâmica 2026")
    assert "usar_modelo_da_galeria" in resultado["tools_usadas"]
    assert resultado.get("mapspec") is not None
    assert mapspec_da_conversa(cid) is not None
    esquecer_conversa(cid)


def test_cassete_sse_deepseek_sem_rede():
    provedor = DeepSeekProvedor("sk-fake", urlopen=opener_de_cassete("sse_ola"))
    textos = []
    for delta in provedor.enviar_stream([MensagemLLM(papel="user", conteudo="oi")]):
        if delta.texto:
            textos.append(delta.texto)
    assert "".join(textos) == "Olá do cassete VCR. Pronto."


def test_mapspec_persiste_em_disco(pasta_chats: Path, pasta_harmonia: Path):
    workspace_servico.abrir(str(pasta_harmonia))
    configurar_provedor(provedor_de_cassete("galeria_dinamica"))
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=str(pasta_harmonia))["conversation_id"]
    repo.fechar()

    executar_turno(conversation_id=cid, mensagem="monta")
    caminho = mapspec_store.caminho_mapspec(cid)
    assert caminho.is_file()
    # solta a memória e recarrega do disco
    esquecer_conversa(cid)
    reloaded = mapspec_da_conversa(cid)
    assert reloaded is not None
    assert reloaded.get("template") or reloaded.get("camadas")
    esquecer_conversa(cid)
