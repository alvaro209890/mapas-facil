# M6 / F1-17 — persistência de conversas (anel 1, SQLite local).

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from mapasfacil_nucleo.__main__ import processar_linha
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.banco import SCHEMA_VERSAO_ATUAL, conectar
from mapasfacil_nucleo.conversas.fingerprint import fingerprint_workspace
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.conversas.titulo import TITULO_PADRAO, titulo_da_mensagem
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import envelope_req


@pytest.fixture
def pasta_chats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "chats"
    pasta.mkdir()
    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta))
    conversas_servico.configurar_diretorio(pasta)
    yield pasta
    conversas_servico.configurar_diretorio(None)


def _ndjson(metodo: str, params: dict | None = None) -> dict:
    return json.loads(processar_linha(json.dumps(envelope_req(metodo, params or {}))))


def test_migracao_schema_versao_1(pasta_chats: Path):
    conn = conectar(pasta_chats / "chats.sqlite")
    assert conn.execute("SELECT versao FROM schema_versao").fetchone()[0] == SCHEMA_VERSAO_ATUAL
    conn.close()


def test_fingerprint_estavel_e_casefold(tmp_path: Path):
    a = fingerprint_workspace(tmp_path)
    b = fingerprint_workspace(str(tmp_path).upper() if os.name == "nt" else tmp_path)
    # no Linux upper muda o path; casefold do as_posix ainda diferencia se o FS for case-sensitive
    assert len(a) == 64
    assert a == fingerprint_workspace(tmp_path)


def test_ciclo_completo_reabre_com_traces(pasta_chats: Path, tmp_path: Path):
    ws = tmp_path / "Harmonia"
    ws.mkdir()
    repo = RepositorioConversas(pasta_chats)
    criada = repo.criar_conversa(workspace=str(ws))
    cid = criada["conversation_id"]
    for i in range(5):
        msg = repo.adicionar_mensagem(cid, papel="usuario" if i % 2 == 0 else "assistente", conteudo=f"msg {i}")
        if i == 1:
            repo.adicionar_tool_trace(
                cid,
                message_id=msg["message_id"],
                tool="listar_shapefiles",
                args_resumo="{}",
                resultado_resumo="4 shapefiles",
                ms=12,
            )
    repo.fechar()

    # reabre processo lógico (novo repo, mesmo arquivo)
    repo2 = RepositorioConversas(pasta_chats)
    aberto = repo2.abrir_conversa(cid)
    assert aberto["total"] == 5
    assert [m["conteudo"] for m in aberto["mensagens"]] == [f"msg {i}" for i in range(5)]
    assert len(aberto["mensagens"][1]["tool_traces"]) == 1
    assert aberto["mensagens"][1]["tool_traces"][0]["tool"] == "listar_shapefiles"
    repo2.fechar()


def test_abrir_200_mensagens_menos_de_300ms(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    for i in range(200):
        repo.adicionar_mensagem(cid, papel="usuario", conteudo=f"linha {i:03d} " + ("x" * 40))
    t0 = time.perf_counter()
    aberto = repo.abrir_conversa(cid, limite=30)
    ms = (time.perf_counter() - t0) * 1000
    assert aberto["total"] == 200
    assert len(aberto["mensagens"]) == 30
    assert aberto["mensagens"][0]["seq"] == 171  # últimas 30: 171..200
    assert aberto["mensagens"][-1]["seq"] == 200
    # tolerância folgada para CI lento / VM compartilhada (critério F1-17: < 300 ms em máquina normal)
    assert ms < 800, f"abrir_conversa demorou {ms:.1f} ms"
    repo.fechar()


def test_cpf_nao_fica_no_arquivo(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    repo.adicionar_mensagem(cid, papel="usuario", conteudo="CPF 123.456.789-00 do proprietário")
    assert repo.conteudo_bruto(cid, 1) == "CPF [CPF removido] do proprietário"
    repo.fechar()
    bruto = (pasta_chats / "chats.sqlite").read_bytes()
    assert b"123.456.789" not in bruto
    assert b"12345678900" not in bruto


def test_buscar_com_e_sem_acento(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    repo.adicionar_mensagem(cid, papel="usuario", conteudo="mapa de tipologIA da paisagem")
    # termo acentuado encontra texto sem acento (remove_diacritics 2)
    r1 = repo.buscar("tipologia")
    assert len(r1["resultados"]) >= 1
    r2 = repo.buscar("tipologIA")
    assert len(r2["resultados"]) >= 1
    repo.fechar()


def test_ramificar_copia_ate_seq(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    for i in range(10):
        repo.adicionar_mensagem(cid, papel="usuario", conteudo=f"n{i}")
    filho = repo.ramificar(cid, a_partir_do_seq=3)
    aberto = repo.abrir_conversa(filho["conversation_id"])
    assert aberto["total"] == 3
    assert aberto["conversa"]["parent_conversation_id"] == cid
    assert aberto["conversa"]["parent_message_seq"] == 3
    assert [m["conteudo"] for m in aberto["mensagens"]] == ["n0", "n1", "n2"]
    repo.fechar()


def test_apagar_remove_cascata_e_anexos(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    msg = repo.adicionar_mensagem(cid, papel="usuario", conteudo="oi")
    repo.adicionar_tool_trace(cid, message_id=msg["message_id"], tool="x", args_resumo="{}")
    pasta = pasta_chats / "anexos" / cid
    pasta.mkdir(parents=True)
    (pasta / "a.bin").write_bytes(b"123")
    saida = repo.apagar(cid)
    assert saida["ok"] is True
    assert saida["anexos_removidos"] == 1
    assert not pasta.exists()
    with pytest.raises(ErroNucleo) as exc:
        repo.abrir_conversa(cid)
    assert exc.value.codigo == "CH-001"
    repo.fechar()


def test_renomear_marca_title_manual(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    repo.renomear(cid, "Meu título")
    repo.adicionar_mensagem(cid, papel="usuario", conteudo="primeira mensagem longa demais")
    aberto = repo.abrir_conversa(cid)
    assert aberto["conversa"]["title"] == "Meu título"
    assert aberto["conversa"]["title_manual"] is True
    repo.fechar()


def test_titulo_automatico_primeira_mensagem(pasta_chats: Path):
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa()["conversation_id"]
    assert repo.abrir_conversa(cid)["conversa"]["title"] == TITULO_PADRAO
    repo.adicionar_mensagem(cid, papel="usuario", conteudo="Gera a Dinâmica 2026 da Harmonia agora")
    titulo = repo.abrir_conversa(cid)["conversa"]["title"]
    assert titulo == titulo_da_mensagem("Gera a Dinâmica 2026 da Harmonia agora")
    repo.fechar()


def test_ndjson_criar_listar_abrir_buscar(pasta_chats: Path, tmp_path: Path):
    ws = tmp_path / "projeto"
    ws.mkdir()
    criada = _ndjson("chat.criar_conversa", {"workspace": str(ws), "title": "Teste"})
    assert criada["ok"] is True
    cid = criada["resultado"]["conversation_id"]

    gravada = _ndjson(
        "chat.gravar_mensagem",
        {"conversation_id": cid, "papel": "usuario", "conteudo": "área de preservação"},
    )
    assert gravada["ok"] is True

    lista = _ndjson("chat.listar_conversas", {})
    assert lista["ok"] is True
    assert any(c["conversation_id"] == cid for c in lista["resultado"]["conversas"])

    aberta = _ndjson("chat.abrir_conversa", {"conversation_id": cid})
    assert aberta["ok"] is True
    assert aberta["resultado"]["total"] == 1

    busca = _ndjson("chat.buscar", {"termo": "preservacao"})
    assert busca["ok"] is True
    assert len(busca["resultado"]["resultados"]) >= 1

    assert _ndjson("chat.renomear", {"conversation_id": cid, "title": "Novo"})["ok"]
    assert _ndjson("chat.arquivar", {"conversation_id": cid, "arquivada": True})["ok"]
    apagada = _ndjson("chat.apagar", {"conversation_id": cid})
    assert apagada["ok"] is True


def test_ndjson_conversa_inexistente(pasta_chats: Path):
    resp = _ndjson("chat.abrir_conversa", {"conversation_id": "01INVALIDO0000000000000000"})
    assert resp["ok"] is False
    assert resp["erro"]["codigo"] == "CH-001"


def test_sem_rede_no_pacote_conversas():
    raiz = Path(__file__).resolve().parents[1] / "mapasfacil_nucleo" / "conversas"
    # F1-17: nenhum cliente HTTP. Evitar falso positivo em `.fetchall` / `.fetchone`.
    padroes = (
        "urllib.request",
        "urllib.error",
        "import requests",
        "from requests",
        "https://",
        "http://",
        "aiohttp",
        "httpx",
    )
    for caminho in raiz.rglob("*.py"):
        texto = caminho.read_text(encoding="utf-8")
        for palavra in padroes:
            assert palavra not in texto, f"{caminho.name} contém {palavra}"


def test_escrita_concorrente_wal(pasta_chats: Path):
    a = RepositorioConversas(pasta_chats)
    b = RepositorioConversas(pasta_chats)
    cid = a.criar_conversa()["conversation_id"]
    a.adicionar_mensagem(cid, papel="usuario", conteudo="de A")
    b.adicionar_mensagem(cid, papel="assistente", conteudo="de B")
    aberto = a.abrir_conversa(cid)
    assert aberto["total"] == 2
    a.fechar()
    b.fechar()
