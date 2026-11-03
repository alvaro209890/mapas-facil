"""W3 — API base: bancos, contas, sessões, CSRF, projetos e permissões."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.auth import contas, senhas, sessoes
from mapasfacil_servidor.db import Banco

API = "/api/v1"
SENHA = "uma-senha-longa-123"


@pytest.fixture
def banco(tmp_path):
    b = Banco(tmp_path / "dados" / "mapasfacil.sqlite")
    assert b.migrar() >= 1
    return b


@pytest.fixture
def con(banco):
    con = banco.conectar()
    yield con
    con.close()


@pytest.fixture
def cliente(banco):
    app = create_app(banco=banco, admin_email="chefe@imap.com.br", origem="https://testserver")
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def cadastrar(cliente, email="ana@imap.com.br", nome="Ana", senha=SENHA):
    return cliente.post(
        f"{API}/auth/cadastrar", json={"nome": nome, "email": email, "senha": senha}
    )


def entrar(cliente, email="ana@imap.com.br", senha=SENHA):
    return cliente.post(f"{API}/auth/entrar", json={"email": email, "senha": senha})


def csrf(cliente) -> str:
    resposta = cliente.get(f"{API}/auth/eu")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["csrf"]


# --- migração -------------------------------------------------------------


def test_migracao_cria_schema_e_e_idempotente(banco):
    assert banco.versao() >= 1
    antes = banco.versao()
    assert banco.migrar() == antes
    con = banco.conectar()
    try:
        tabelas = {
            linha[0]
            for linha in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        con.close()
    assert {"usuarios", "sessoes", "auditoria", "projetos", "versoes"} <= tabelas


# --- senhas ---------------------------------------------------------------


def test_hash_nao_guarda_a_senha_e_confere():
    hash_armazenado = senhas.gerar_hash(SENHA)
    assert SENHA not in hash_armazenado
    assert hash_armazenado.startswith("scrypt$")
    assert senhas.conferir(SENHA, hash_armazenado) is True
    assert senhas.conferir("outra-senha-123", hash_armazenado) is False


def test_senha_fraca_e_recusada():
    assert senhas.problemas("curta") is not None
    assert senhas.problemas("123456") is not None
    assert senhas.problemas("aaaaaaaaaaaa") is not None  # poucos caracteres distintos
    assert senhas.problemas("uma-senha-longa-123") is None


def test_email_conservador():
    assert senhas.conferir_email("a@b.com")
    for ruim in ("semarroba.com", "a@b", "a@@b.com", "a b@c.com", "@b.com"):
        assert not senhas.conferir_email(ruim), ruim


# --- cadastro e login -----------------------------------------------------


def test_cadastro_abre_sessao_e_devolve_csrf(cliente):
    resposta = cadastrar(cliente)
    assert resposta.status_code == 201, resposta.text
    usuario = resposta.json()["usuario"]
    assert usuario["email"] == "ana@imap.com.br"
    assert usuario["papel"] == "usuario"
    assert usuario["trocar_senha"] is False
    assert SENHA not in resposta.text
    assert '"senha"' not in resposta.text

    eu = cliente.get(f"{API}/auth/eu")
    assert eu.status_code == 200
    assert eu.json()["csrf"]
    assert eu.json()["usuario"]["id"] == usuario["id"]


def test_email_duplicado_409(cliente):
    cadastrar(cliente)
    cliente.post(f"{API}/auth/sair")
    resposta = cadastrar(cliente, email="ANA@imap.com.br")
    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "SV-012"


def test_senha_fraca_400_e_email_invalido_400(cliente):
    fraca = cliente.post(
        f"{API}/auth/cadastrar", json={"nome": "X", "email": "x@y.com", "senha": "123456"}
    )
    assert fraca.status_code == 400
    assert fraca.json()["erro"]["codigo"] == "SV-010"

    invalido = cliente.post(
        f"{API}/auth/cadastrar", json={"nome": "X", "email": "x", "senha": SENHA}
    )
    assert invalido.status_code == 400
    assert invalido.json()["erro"]["codigo"] == "SV-013"


def test_primeiro_admin_vem_do_mf_admin_email(cliente):
    resposta = cadastrar(cliente, email="chefe@imap.com.br", nome="Chefe")
    assert resposta.status_code == 201
    assert resposta.json()["usuario"]["papel"] == "admin"


def test_login_errado_401_sem_vazar_existencia(cliente):
    cadastrar(cliente)
    cliente.post(f"{API}/auth/sair")
    errado = entrar(cliente, senha="senha-errada-123")
    inexistente = entrar(cliente, email="ninguem@imap.com.br")
    assert errado.status_code == inexistente.status_code == 401
    assert errado.json()["erro"]["codigo"] == inexistente.json()["erro"]["codigo"] == "SV-001"
    assert errado.json()["erro"]["mensagem"] == inexistente.json()["erro"]["mensagem"]


def test_conta_bloqueada_403_e_sessoes_caem(cliente, con):
    cadastrar(cliente)
    usuario_id = cliente.get(f"{API}/auth/eu").json()["usuario"]["id"]
    contas.bloquear(con, usuario_id=usuario_id, ativo=False, autor_id=None)

    assert cliente.get(f"{API}/auth/eu").status_code == 401
    resposta = entrar(cliente)
    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "SV-003"


def test_limitador_apos_cinco_falhas_429(cliente):
    cadastrar(cliente)
    cliente.post(f"{API}/auth/sair")
    for _ in range(5):
        assert entrar(cliente, senha="senha-errada-123").status_code == 401
    resposta = entrar(cliente, senha="senha-errada-123")
    assert resposta.status_code == 429
    assert resposta.json()["erro"]["codigo"] == "SV-005"


def test_sair_apaga_sessao(cliente):
    cadastrar(cliente)
    assert cliente.post(f"{API}/auth/sair").status_code == 204
    assert cliente.get(f"{API}/auth/eu").status_code == 401


# --- CSRF -----------------------------------------------------------------


def test_mutacao_sem_csrf_403(cliente):
    cadastrar(cliente)
    resposta = cliente.post(
        f"{API}/projetos", json={"nome": "P1", "folha": {"formato": "A4"}}
    )
    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "SV-020"


def test_mutacao_com_csrf_errado_403(cliente):
    cadastrar(cliente)
    resposta = cliente.post(
        f"{API}/projetos",
        json={"nome": "P1", "folha": {"formato": "A4"}},
        headers={"X-MF-CSRF": "errado"},
    )
    assert resposta.status_code == 403


def test_origem_estranha_403(cliente):
    cadastrar(cliente)
    token = csrf(cliente)
    resposta = cliente.post(
        f"{API}/projetos",
        json={"nome": "P1", "folha": {"formato": "A4"}},
        headers={"X-MF-CSRF": token, "Origin": "https://site-malicioso.example"},
    )
    assert resposta.status_code == 403
    assert resposta.json()["erro"]["codigo"] == "SV-021"


# --- projetos -------------------------------------------------------------


def criar_projeto(cliente, nome="Boa Vista", formato="A4", orientacao="retrato"):
    return cliente.post(
        f"{API}/projetos",
        json={"nome": nome, "folha": {"formato": formato, "orientacao": orientacao}},
        headers={"X-MF-CSRF": csrf(cliente)},
    )


def test_criar_projeto_comeca_aguardando_zip(cliente):
    cadastrar(cliente)
    resposta = criar_projeto(cliente)
    assert resposta.status_code == 201, resposta.text
    projeto = resposta.json()["projeto"]
    assert projeto["estado"] == "aguardando_zip"
    assert projeto["folha"] == {"formato": "A4", "orientacao": "retrato"}
    assert projeto["versao_atual"] == 0


def test_folha_invalida_400(cliente):
    cadastrar(cliente)
    assert criar_projeto(cliente, formato="A7").status_code == 400
    assert criar_projeto(cliente, orientacao="diagonal").status_code == 400


def test_listar_pagina_e_filtra(cliente):
    cadastrar(cliente)
    for i in range(3):
        criar_projeto(cliente, nome=f"Projeto {i}")
    pagina = cliente.get(f"{API}/projetos", params={"limite": 2})
    assert pagina.status_code == 200
    corpo = pagina.json()
    assert len(corpo["itens"]) == 2
    assert corpo["proximo"]

    proxima = cliente.get(f"{API}/projetos", params={"limite": 2, "antes": corpo["proximo"]})
    assert len(proxima.json()["itens"]) == 1

    filtrado = cliente.get(f"{API}/projetos", params={"busca": "Projeto 1"})
    assert [p["nome"] for p in filtrado.json()["itens"]] == ["Projeto 1"]


def test_projeto_de_outro_usuario_e_404(cliente):
    cadastrar(cliente, email="ana@imap.com.br", nome="Ana")
    projeto_id = criar_projeto(cliente, nome="Da Ana").json()["projeto"]["id"]
    cliente.post(f"{API}/auth/sair")

    cadastrar(cliente, email="bia@imap.com.br", nome="Bia")
    assert cliente.get(f"{API}/projetos/{projeto_id}").status_code == 404
    assert (
        cliente.get(f"{API}/projetos/{projeto_id}").json()["erro"]["codigo"] == "SV-031"
    )
    assert cliente.get(f"{API}/projetos").json()["itens"] == []


def test_admin_le_projeto_alheio(cliente, con):
    cadastrar(cliente, email="ana@imap.com.br", nome="Ana")
    projeto_id = criar_projeto(cliente, nome="Da Ana").json()["projeto"]["id"]
    cliente.post(f"{API}/auth/sair")

    admin = contas.criar(
        con,
        nome="Chefe",
        email="chefe@imap.com.br",
        senha=SENHA,
        admin_email="chefe@imap.com.br",
    )
    assert admin.papel == "admin"
    entrar(cliente, email="chefe@imap.com.br")
    resposta = cliente.get(f"{API}/projetos/{projeto_id}")
    assert resposta.status_code == 200
    assert resposta.json()["projeto"]["nome"] == "Da Ana"


def test_apagar_vai_para_lixeira_e_restaurar_volta(cliente):
    cadastrar(cliente)
    projeto_id = criar_projeto(cliente).json()["projeto"]["id"]
    token = csrf(cliente)
    assert cliente.delete(f"{API}/projetos/{projeto_id}", headers={"X-MF-CSRF": token}).status_code == 204

    listado = cliente.get(f"{API}/projetos").json()["itens"]
    assert listado == []
    na_lixeira = cliente.get(f"{API}/projetos", params={"estado": "lixeira"}).json()["itens"]
    assert len(na_lixeira) == 1

    volta = cliente.post(f"{API}/projetos/{projeto_id}/restaurar", headers={"X-MF-CSRF": token})
    assert volta.status_code == 200
    assert volta.json()["projeto"]["estado"] == "aguardando_zip"


def test_renomear(cliente):
    cadastrar(cliente)
    projeto_id = criar_projeto(cliente).json()["projeto"]["id"]
    resposta = cliente.patch(
        f"{API}/projetos/{projeto_id}",
        json={"nome": "Novo nome"},
        headers={"X-MF-CSRF": csrf(cliente)},
    )
    assert resposta.status_code == 200
    assert resposta.json()["projeto"]["nome"] == "Novo nome"


def test_transicao_invalida_sv090(cliente, banco):
    from mapasfacil_servidor import projetos_repo

    con = banco.conectar()
    try:
        usuario = contas.criar(con, nome="Ana", email="ana@imap.com.br", senha=SENHA)
        projeto = projetos_repo.criar(
            con, usuario_id=usuario.id, nome="P", folha={"formato": "A4"}
        )
        with pytest.raises(Exception) as exc:
            projetos_repo.transicionar(con, projeto, "pronto")
        assert exc.value.codigo == "SV-090"
    finally:
        con.close()


def test_saude_e_publica_e_sem_dado_de_usuario(cliente):
    resposta = cliente.get(f"{API}/saude")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ok"] is True
    assert "@" not in resposta.text


# --- admin ----------------------------------------------------------------


def test_admin_lista_cria_e_bloqueia(cliente, con):
    cadastrar(cliente, email="chefe@imap.com.br", nome="Chefe")
    token = csrf(cliente)

    criado = cliente.post(
        f"{API}/admin/usuarios",
        json={"email": "novo@imap.com.br", "nome": "Novo", "papel": "usuario"},
        headers={"X-MF-CSRF": token},
    )
    assert criado.status_code == 201
    assert criado.json()["usuario"]["trocar_senha"] is True
    assert criado.json()["senha_temporaria"]

    lista = cliente.get(f"{API}/admin/usuarios")
    assert lista.status_code == 200
    assert {u["email"] for u in lista.json()["itens"]} == {
        "chefe@imap.com.br",
        "novo@imap.com.br",
    }

    alvo = criado.json()["usuario"]["id"]
    bloqueio = cliente.patch(
        f"{API}/admin/usuarios/{alvo}",
        json={"ativo": False},
        headers={"X-MF-CSRF": token},
    )
    assert bloqueio.status_code == 200
    assert bloqueio.json()["usuario"]["ativo"] is False


def test_usuario_comum_nao_entra_no_admin(cliente):
    cadastrar(cliente, email="ana@imap.com.br")
    assert cliente.get(f"{API}/admin/usuarios").status_code == 403
    assert cliente.get(f"{API}/admin/auditoria").status_code == 403


def test_auditoria_registra_cadastro_e_login(cliente):
    cadastrar(cliente, email="chefe@imap.com.br", nome="Chefe")
    cliente.post(f"{API}/auth/sair")
    entrar(cliente, email="chefe@imap.com.br")
    resposta = cliente.get(f"{API}/admin/auditoria")
    assert resposta.status_code == 200
    acoes = [item["acao"] for item in resposta.json()["itens"]]
    assert "cadastrou" in acoes and "entrou" in acoes


# --- sessões (unidade) ----------------------------------------------------


def test_sessao_expira_e_e_apagada(con, banco):
    usuario = contas.criar(con, nome="Ana", email="ana@imap.com.br", senha=SENHA)
    token, sessao = sessoes.criar(con, usuario_id=usuario.id)
    assert sessoes.obter(con, token).usuario_id == usuario.id
    con.execute(
        "UPDATE sessoes SET expira_em = '2000-01-01T00:00:00Z' WHERE id_hash = ?",
        (sessao.id_hash,),
    )
    assert sessoes.obter(con, token) is None


def test_token_nao_fica_em_claro_no_banco(con):
    usuario = contas.criar(con, nome="Ana", email="ana@imap.com.br", senha=SENHA)
    token, _ = sessoes.criar(con, usuario_id=usuario.id)
    linhas = con.execute("SELECT id_hash FROM sessoes").fetchall()
    assert token not in [linha["id_hash"] for linha in linhas]
    assert len(linhas[0]["id_hash"]) == 64
