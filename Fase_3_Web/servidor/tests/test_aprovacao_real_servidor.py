"""Testes reais do fluxo de aprovação segura no servidor.

Testa:
- GET /projetos/{id}/agente publica token apenas para owner/agente autenticado;
- GET detecta TTL expirado;
- POST com CSRF confere token constante, action, path, version, hash e TTL;
- POST grava atomicamente decisao.json e não confia em estado fabricável de .agente/estado.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor import db, projetos_repo
from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.auth import contas, sessoes
from mapasfacil_servidor.config import carregar
from mapasfacil_servidor.versoes_sync import raiz_do_projeto

API = "/api/v1"
SENHA = "senha-muito-segura-123"


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
    monkeypatch.setenv("MF_ADMIN_EMAIL", "chefe@imap.com.br")
    cfg = carregar()
    banco = db.Banco(cfg.banco)
    banco.migrar()
    app = create_app(
        banco=banco,
        admin_email=cfg.admin_email,
        origem="https://testserver",
        config=cfg,
    )
    with TestClient(app, base_url="https://testserver") as c:
        yield c, cfg, banco, app


def cadastrar(cliente, email="proprietario@teste.com", nome="Proprietário", senha=SENHA):
    return cliente.post(
        f"{API}/auth/cadastrar", json={"nome": nome, "email": email, "senha": senha}
    )


def obter_csrf(cliente) -> str:
    resposta = cliente.get(f"{API}/auth/eu")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["csrf"]


@pytest.fixture
def cliente_autenticado(ambiente):
    client, cfg, banco, app = ambiente
    cad = cadastrar(client)
    assert cad.status_code == 201, cad.text
    usuario_info = cad.json()["usuario"]
    token_csrf = obter_csrf(client)
    resp_proj = client.post(
        f"{API}/projetos",
        headers={"X-MF-CSRF": token_csrf},
        json={"nome": "Projeto Aprovacao", "folha": {"formato": "A4", "orientacao": "retrato"}},
    )
    assert resp_proj.status_code == 201, resp_proj.text
    projeto_id = resp_proj.json()["projeto"]["id"]
    return client, token_csrf, usuario_info, projeto_id, app


def test_get_agente_sem_pedido_retorna_nulo(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    resp = client.get(f"{API}/projetos/{proj_id}/agente")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados.get("aprovacao") is None
    assert dados.get("pedido_pendente") is None


def test_get_agente_publica_token_do_pedido(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)

    pedido_dados = {
        "token": "tok_secreto_12345",
        "action": "excluir_camada",
        "path": "SHP/teste.shp",
        "version": 1,
        "hash": "abc123hash",
        "ttl": 300,
        "timestamp": time.time(),
        "motivo": "Remover camada obsoleta",
    }
    (pasta_aprov / "pedido.json").write_text(json.dumps(pedido_dados), encoding="utf-8")

    resp = client.get(f"{API}/projetos/{proj_id}/agente")
    assert resp.status_code == 200
    dados = resp.json()
    aprov = dados.get("aprovacao")
    assert aprov is not None
    assert aprov["status"] == "pendente"
    assert aprov["token"] == "tok_secreto_12345"
    assert aprov["action"] == "excluir_camada"
    assert aprov["path"] == "SHP/teste.shp"
    assert aprov["version"] == 1
    assert aprov["hash"] == "abc123hash"
    # Contrato consumido pelo botão de aprovação do frontend (NDJSON + reload).
    assert aprov["acao"] == "excluir_camada"
    assert aprov["caminho"] == "SHP/teste.shp"


def test_get_agente_detecta_ttl_expirado(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)

    pedido_expirado = {
        "token": "tok_expirado_999",
        "action": "editar",
        "ttl": 10,
        "timestamp": time.time() - 20,  # 20 segundos atrás com TTL 10
    }
    (pasta_aprov / "pedido.json").write_text(json.dumps(pedido_expirado), encoding="utf-8")

    resp = client.get(f"{API}/projetos/{proj_id}/agente")
    assert resp.status_code == 200
    dados = resp.json()
    aprov = dados.get("aprovacao")
    assert aprov is not None
    assert aprov["status"] == "expirado"
    assert aprov.get("expirado") is True


def test_post_aprovacao_recusa_sem_csrf(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    resp = client.post(
        f"{API}/projetos/{proj_id}/agente/aprovacao",
        json={"acao": "aprovar", "token": "qualquer"},
    )
    assert resp.status_code == 403


def test_post_aprovacao_token_invalido_retorna_403(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)

    pedido = {
        "token": "token_correto_xyz",
        "action": "deletar",
        "ttl": 300,
        "timestamp": time.time(),
    }
    (pasta_aprov / "pedido.json").write_text(json.dumps(pedido), encoding="utf-8")

    resp = client.post(
        f"{API}/projetos/{proj_id}/agente/aprovacao",
        headers={"X-MF-CSRF": csrf_tok},
        json={"acao": "aprovar", "token": "token_errado_abc"},
    )
    assert resp.status_code == 403
    assert resp.json()["erro"]["codigo"] == "SV-098"


def test_post_aprovacao_ttl_expirado_retorna_400(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)

    pedido = {
        "token": "token_valido",
        "action": "deletar",
        "ttl": 5,
        "timestamp": time.time() - 10,
    }
    (pasta_aprov / "pedido.json").write_text(json.dumps(pedido), encoding="utf-8")

    resp = client.post(
        f"{API}/projetos/{proj_id}/agente/aprovacao",
        headers={"X-MF-CSRF": csrf_tok},
        json={"acao": "aprovar", "token": "token_valido"},
    )
    assert resp.status_code == 400
    assert resp.json()["erro"]["codigo"] == "SV-097"


def test_post_aprovacao_divergencia_metadados_retorna_400(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)

    pedido = {
        "token": "token_valido",
        "action": "deletar_camada",
        "path": "SHP/ATP.shp",
        "version": 2,
        "hash": "hash_original",
        "ttl": 300,
        "timestamp": time.time(),
    }
    (pasta_aprov / "pedido.json").write_text(json.dumps(pedido), encoding="utf-8")

    # Informa path divergente
    resp = client.post(
        f"{API}/projetos/{proj_id}/agente/aprovacao",
        headers={"X-MF-CSRF": csrf_tok},
        json={"acao": "aprovar", "token": "token_valido", "path": "SHP/OUTRO.shp"},
    )
    assert resp.status_code == 400
    assert resp.json()["erro"]["codigo"] == "SV-099"


def test_post_aprovacao_sucesso_grava_decisao_atomica(cliente_autenticado):
    client, csrf_tok, usuario, proj_id, app = cliente_autenticado
    raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)

    # Cria pedido
    pedido = {
        "token": "token_legitimo_987",
        "action": "ajustar_perimetro",
        "path": "SHP/ATP.shp",
        "version": 1,
        "hash": "h_12345",
        "ttl": 300,
        "timestamp": time.time(),
        "motivo": "Reancoragem pelo usuário",
    }
    (pasta_aprov / "pedido.json").write_text(json.dumps(pedido), encoding="utf-8")

    # Cria .agente/estado.json fictício para garantir que NÃO é sobrescrito como fabricável
    pasta_agente = raiz / ".agente"
    pasta_agente.mkdir(parents=True, exist_ok=True)
    estado_original = {"status": "intocado", "passos": ["p1"]}
    (pasta_agente / "estado.json").write_text(json.dumps(estado_original), encoding="utf-8")

    resp = client.post(
        f"{API}/projetos/{proj_id}/agente/aprovacao",
        headers={"X-MF-CSRF": csrf_tok},
        json={
            "acao": "aprovar",
            "token": "token_legitimo_987",
            "action": "ajustar_perimetro",
            "path": "SHP/ATP.shp",
            "version": 1,
            "hash": "h_12345",
            "motivo": "Confirmado pelo proprietário",
        },
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["ok"] is True
    assert corpo["status"] == "aprovado"

    # Confere decisao.json gravado
    decisao_file = pasta_aprov / "decisao.json"
    assert decisao_file.is_file()
    decisao = json.loads(decisao_file.read_text(encoding="utf-8"))
    assert decisao["status"] == "aprovado"
    assert decisao["token"] == "token_legitimo_987"
    assert decisao["action"] == "ajustar_perimetro"
    assert decisao["path"] == "SHP/ATP.shp"
    assert decisao["usuario_id"] == usuario["id"]
    assert decisao["usuario_nome"] == usuario["nome"]
    assert decisao["motivo"] == "Confirmado pelo proprietário"

    # Confere que o pedido permanece com status='aprovado' para ser consumido pelo núcleo
    assert (pasta_aprov / "pedido.json").is_file()
    pedido_gravado = json.loads((pasta_aprov / "pedido.json").read_text(encoding="utf-8"))
    assert pedido_gravado["status"] == "aprovado"

    # Confere que .agente/estado.json permaneceu intocado (read-only)
    conteudo_agente = json.loads((pasta_agente / "estado.json").read_text(encoding="utf-8"))
    assert conteudo_agente == estado_original
