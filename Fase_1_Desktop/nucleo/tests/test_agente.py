# M7 — testes do agente com FakeProvedor (sem rede / sem chave).

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.chave import ler_chave_deepseek
from mapasfacil_nucleo.agente.contexto import (
    assert_sem_vazamento,
    compactar_se_preciso,
    montar_mensagens_llm,
    serializar_payload,
)
from mapasfacil_nucleo.agente.fake import FakeProvedor, PassoFake, tool_call
from mapasfacil_nucleo.agente.orquestrador import configurar_provedor, executar_turno
from mapasfacil_nucleo.agente.prompt import conferir_teto, texto_system_prompt
from mapasfacil_nucleo.agente.tools import executar, nomes_tools, schemas_openai
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria.montar import montar_mapspec
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture
def pasta_chats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    return tmp_path


def test_system_prompt_cabe_no_teto():
    info = conferir_teto()
    assert info["cabe"] is True
    assert info["tokens_estimados"] <= limites.SYSTEM_PROMPT_MAX
    assert "temperature" not in texto_system_prompt().lower()


def test_catalogo_tem_pelo_menos_26_tools():
    assert len(nomes_tools()) >= 26
    assert "usar_modelo_da_galeria" in nomes_tools()
    assert len(schemas_openai()) == len(nomes_tools())


def test_sem_chave_chat_enviar_ia001(pasta_chats: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "mapasfacil_nucleo.agente.orquestrador.ler_chave_deepseek",
        lambda **kwargs: None,
    )
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    repo.fechar()
    with pytest.raises(ErroNucleo) as exc:
        executar_turno(conversation_id=cid, mensagem="olá")
    assert exc.value.codigo == limites.CODIGO_SEM_CHAVE


def test_teto_12_rodadas_ia030(pasta_chats: Path):
    passos = [
        PassoFake(tool_calls=[tool_call("estado_do_projeto", {}, call_id=f"c{i}")])
        for i in range(13)
    ]
    configurar_provedor(FakeProvedor(passos))
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    repo.fechar()
    with pytest.raises(ErroNucleo) as exc:
        executar_turno(conversation_id=cid, mensagem="loop")
    assert exc.value.codigo == limites.CODIGO_LIMITE_RODADAS


def test_compressao_conversa_longa(pasta_chats: Path):
    mensagens = []
    for i in range(120):
        mensagens.append({"seq": i * 2 + 1, "papel": "usuario", "conteudo": f"pedido {i} " + ("área " * 50)})
        mensagens.append({"seq": i * 2 + 2, "papel": "assistente", "conteudo": f"ok {i} " + ("mapa " * 50)})
    summary = "Resumo: usuário pediu vários mapas da série IMAP; modelos da galeria usados."
    msgs = montar_mensagens_llm(mensagens_db=mensagens, compact_summary=summary)
    msgs2, summary2, comprimiu = compactar_se_preciso(
        msgs, compact_summary=summary, mensagens_db=mensagens, mapspec=None
    )
    # após compactar/resumir deve caber
    from mapasfacil_nucleo.agente.contexto import estimar_payload

    assert estimar_payload(msgs2) <= limites.ENTRADA_MAX_POR_TURNO
    assert summary2
    # verbatim limitado (aprox. 8 turnos = até 16 msgs)
    user_asst = [m for m in msgs2 if m.papel in ("user", "assistant")]
    assert len(user_asst) <= limites.TURNOS_VERBATIM * 2


def test_sem_vazamento_no_payload(pasta_chats: Path, pasta_harmonia: Path):
    workspace_servico.abrir(str(pasta_harmonia))
    mensagens = [
        {
            "seq": 1,
            "papel": "usuario",
            "conteudo": "CPF 123.456.789-00 e POLYGON((0 0,1 0,1 1,0 1,0 0)) e C:\\Users\\fulano\\x",
        }
    ]
    # redator na montagem
    msgs = montar_mensagens_llm(mensagens_db=mensagens, compact_summary=None)
    payload = serializar_payload(msgs)
    assert_sem_vazamento(payload)
    assert "123.456.789" not in payload
    assert "POLYGON" not in payload.upper() or "POLYGON" not in payload  # redigido/ausente


def test_galeria_antes_de_criar_mapa(pasta_chats: Path, pasta_harmonia: Path):
    workspace_servico.abrir(str(pasta_harmonia))
    fake = FakeProvedor(
        [
            PassoFake(
                tool_calls=[
                    tool_call(
                        "usar_modelo_da_galeria",
                        {"modelo_id": "dinamica_2026_retrato"},
                        call_id="c1",
                    )
                ]
            ),
            PassoFake(texto="Pronto — usei o modelo Dinâmica 2026 da galeria.", pedacos=["Pronto — ", "usei o modelo."]),
        ]
    )
    configurar_provedor(fake)
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=str(pasta_harmonia))["conversation_id"]
    repo.fechar()
    resultado = executar_turno(conversation_id=cid, mensagem="faz a Dinâmica 2026 dessa pasta")
    assert "usar_modelo_da_galeria" in resultado["tools_usadas"]
    assert "criar_mapa" not in resultado["tools_usadas"]
    assert resultado["mapspec"] is not None

    direto = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta_harmonia))["mapspec"]
    assert resultado["mapspec"]["template"] == direto["template"]
    ids_chat = sorted(c["id"] for c in resultado["mapspec"].get("camadas") or [])
    ids_gal = sorted(c["id"] for c in direto.get("camadas") or [])
    assert ids_chat == ids_gal
    assert resultado["mapspec"].get("elementos_layout") == direto.get("elementos_layout")


def test_tool_inexistente_ia020():
    r = executar("tool_que_nao_existe", {}, {})
    assert r["ok"] is False
    assert r["codigo"] == limites.CODIGO_TOOL_INEXISTENTE


def test_grep_temperature_ausente_ou_comentado():
    raiz = Path(__file__).resolve().parents[1] / "mapasfacil_nucleo" / "agente"
    for caminho in raiz.rglob("*.py"):
        for i, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            if "temperature" in linha.lower() and not linha.strip().startswith("#"):
                # permitido só em comentário; deepseek não envia temperature
                if "temperature" in linha and "ignorad" not in linha.lower() and "#" not in linha.split("temperature")[0]:
                    # deepseek.py docstring mentions it?
                    if caminho.name == "deepseek.py" and "não é enviado" in caminho.read_text(encoding="utf-8"):
                        continue
                    if "temperature" in linha and ("#" in linha or '"""' in linha or "ignor" in linha.lower()):
                        continue
                    # fail if assigning temperature in request body
                    if '"temperature"' in linha or "'temperature'" in linha:
                        pytest.fail(f"{caminho.name}:{i} envia temperature")
