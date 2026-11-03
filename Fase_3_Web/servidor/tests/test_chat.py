"""W5-10/W5-11 — chat do projeto: turno, conversa principal e eventos.

Usa a ponte **de verdade** (subprocesso do núcleo falso), então o caminho testado é o
mesmo da produção: `chat.criar_conversa` na primeira mensagem, `chat.enviar` com deltas
pelo SSE e `nucleo.res` fechando o turno.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.config import carregar
from mapasfacil_servidor.db import Banco
from mapasfacil_servidor.ponte import pool as pool_mod
from mapasfacil_servidor.ponte.worker import montar_env

API = "/api/v1"
SENHA = "uma-senha-longa-123"
ROTEIROS = Path(__file__).resolve().parent / "roteiros"
RAIZ_SERVIDOR = Path(__file__).resolve().parents[1]


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text(
        "MAPASFACIL_PROVEDOR_CHAVE=chave-de-teste\n"
        "MAPASFACIL_SEMA_AUTHKEY=sema-de-teste\n"
        "MAPASFACIL_PLANET_API_KEY=planet-de-teste\n",
        encoding="utf-8",
    )
    segredos.chmod(0o600)
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    cfg = carregar()
    banco = Banco(cfg.banco)
    banco.migrar()

    cmd = [
        sys.executable,
        "-m",
        "mapasfacil_servidor.ponte.fake_nucleo",
        "--roteiro",
        str(ROTEIROS / "chat_ok.ndjson"),
    ]
    pool = pool_mod.Pool(
        raiz_projetos=cfg.projetos,
        cmd_base=cmd,
        max_workers=2,
        timeout_req_s=30.0,
        env_por_projeto=lambda pid, raiz_projeto: montar_env(
            projeto_raiz=raiz_projeto,
            usuario_id="usuario_01",
            extra={"PYTHONPATH": str(RAIZ_SERVIDOR)},
        ),
    )
    app = create_app(
        banco=banco,
        admin_email=None,
        origem="https://testserver",
        config=cfg,
        pool=pool,
    )
    with TestClient(app, base_url="https://testserver") as cliente:
        yield cliente, cfg, banco, pool


def cadastrar_e_projeto(cliente):
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Ana", "email": "ana@imap.com.br", "senha": SENHA},
    )
    csrf = cliente.get(f"{API}/auth/eu").json()["csrf"]
    projeto = cliente.post(
        f"{API}/projetos",
        json={"nome": "Boa Vista", "folha": {"formato": "A4", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": csrf},
    ).json()["projeto"]
    return csrf, projeto


def eventos_do_projeto(cfg, projeto_id: str) -> list[dict]:
    caminho = cfg.projetos / projeto_id / ".servidor" / "eventos.ndjson"
    if not caminho.is_file():
        return []
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


def test_primeira_mensagem_cria_conversa_e_emite_eventos(ambiente):
    cliente, cfg, banco, pool = ambiente
    csrf, projeto = cadastrar_e_projeto(cliente)

    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/mensagens",
        json={"texto": "faz a dinâmica 2026"},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 202, resposta.text
    req_id = resposta.json()["req_id"]
    assert req_id

    eventos = eventos_do_projeto(cfg, projeto["id"])
    nomes = [e["evento"] for e in eventos]
    assert "mensagem.criada" in nomes
    assert nomes.count("chat.delta") == 2
    assert "chat.tool" in nomes
    assert nomes[-1] == "nucleo.res"
    assert eventos[-1]["dados"]["req_id"] == req_id
    assert eventos[-1]["dados"]["ok"] is True
    # todos os eventos do turno carregam o req_id da mensagem
    assert {e["req_id"] for e in eventos if e["evento"].startswith("chat.")} == {req_id}
    # sequência estritamente crescente, sem buraco
    assert [e["seq"] for e in eventos] == list(range(1, len(eventos) + 1))

    # a conversa ficou guardada no projeto
    con = banco.conectar()
    try:
        linha = con.execute(
            "SELECT conversa_id FROM projetos WHERE id = ?", (projeto["id"],)
        ).fetchone()
    finally:
        con.close()
    assert linha["conversa_id"] == "c1"

    lista = cliente.get(f"{API}/projetos/{projeto['id']}/mensagens")
    assert lista.status_code == 200
    assert len(lista.json()["itens"]) == 2


def test_segunda_mensagem_reusa_a_conversa(ambiente):
    cliente, cfg, banco, pool = ambiente
    csrf, projeto = cadastrar_e_projeto(cliente)
    for texto in ("primeira", "segunda"):
        assert (
            cliente.post(
                f"{API}/projetos/{projeto['id']}/mensagens",
                json={"texto": texto},
                headers={"X-MF-CSRF": csrf},
            ).status_code
            == 202
        )
    eventos = eventos_do_projeto(cfg, projeto["id"])
    criadas = [e for e in eventos if e["evento"] == "mensagem.criada"]
    assert [e["dados"]["mensagem"]["texto"] for e in criadas] == ["primeira", "segunda"]
    assert [e["evento"] for e in eventos].count("nucleo.res") == 2
    # só uma conversa criada, na primeira mensagem — o roteiro só responde uma vez;
    # se chamasse de novo, o worker devolveria o mesmo id e não haveria erro, então
    # garantimos pela coluna do banco:
    con = banco.conectar()
    try:
        linha = con.execute(
            "SELECT conversa_id FROM projetos WHERE id = ?", (projeto["id"],)
        ).fetchone()
    finally:
        con.close()
    assert linha["conversa_id"] == "c1"


def test_mensagem_vazia_422(ambiente):
    cliente, _, _, _ = ambiente
    csrf, projeto = cadastrar_e_projeto(cliente)
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/mensagens",
        json={"texto": ""},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 422


def test_mensagem_sem_csrf_403(ambiente):
    cliente, _, _, _ = ambiente
    _csrf, projeto = cadastrar_e_projeto(cliente)
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/mensagens", json={"texto": "oi"}
    )
    assert resposta.status_code == 403


def test_mensagem_em_projeto_alheio_404(ambiente):
    cliente, _, _, _ = ambiente
    _csrf, projeto = cadastrar_e_projeto(cliente)
    cliente.post(f"{API}/auth/sair")
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Bia", "email": "bia@imap.com.br", "senha": SENHA},
    )
    csrf2 = cliente.get(f"{API}/auth/eu").json()["csrf"]
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/mensagens",
        json={"texto": "oi"},
        headers={"X-MF-CSRF": csrf2},
    )
    assert resposta.status_code == 404


def test_cancelar_turno(ambiente):
    cliente, _, _, _ = ambiente
    csrf, projeto = cadastrar_e_projeto(cliente)
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/cancelar",
        json={"req_id": "abc123"},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 202
    assert resposta.json()["cancelado"] == "abc123"


def test_sem_pool_devolve_sv240(tmp_path, monkeypatch):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text(
        "MAPASFACIL_PROVEDOR_CHAVE=c\nMAPASFACIL_SEMA_AUTHKEY=s\nMAPASFACIL_PLANET_API_KEY=p\n",
        encoding="utf-8",
    )
    segredos.chmod(0o600)
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    cfg = carregar()
    banco = Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, origem="https://testserver", config=cfg)
    with TestClient(app, base_url="https://testserver") as cliente:
        csrf, projeto = cadastrar_e_projeto(cliente)
        resposta = cliente.post(
            f"{API}/projetos/{projeto['id']}/mensagens",
            json={"texto": "oi"},
            headers={"X-MF-CSRF": csrf},
        )
        assert resposta.status_code == 503
        assert resposta.json()["erro"]["codigo"] == "SV-240"


def test_env_do_worker_isola_estado_por_projeto(tmp_path):
    env = montar_env(projeto_raiz=tmp_path / "p1", usuario_id="u1")
    assert env["MAPASFACIL_DADOS"] == str(tmp_path / "p1" / ".estado")
    assert Path(env["MAPASFACIL_CHATS_DIR"]) == tmp_path / "p1" / ".estado" / "chats"
    assert env["MAPASFACIL_MODO"] == "servidor"


def test_resposta_a_pergunta_sem_texto_e_aceita(ambiente):
    """W5-21: clique num chip/opção envia corpo com `resposta` e texto vazio."""
    cliente, _, _, _ = ambiente
    csrf, projeto = cadastrar_e_projeto(cliente)
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/mensagens",
        json={"resposta": {"pergunta_id": "p123", "selecionados": ["2020"]}},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 202
    assert "req_id" in resposta.json()
