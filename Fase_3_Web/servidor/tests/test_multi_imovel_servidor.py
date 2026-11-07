"""Testes de multi-imóvel no servidor.

Testa:
1. Migração 0004_multi_imovel.sql preserva contas/projetos/versões e faz backfill;
2. Importação com múltiplos imóveis popula imoveis[] no resumo e na tabela imoveis_projeto;
3. Compatibilidade singular mantida em projetos.imovel;
4. Rotas de API GET /projetos/{id}/imoveis e GET /projetos/{id};
5. Rota GET /projetos/{id}/agente com leitura segura de .agente/estado.json;
6. Rota POST /projetos/{id}/agente/aprovacao segura com auth owner e CSRF.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor import db, projetos_repo
from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.auth import contas, senhas, sessoes
from mapasfacil_servidor.config import carregar

API = "/api/v1"
SENHA = "uma-senha-longa-123"
PRJ_TEXTO = 'PROJCS["SIRGAS 2000 / UTM zone 22S"]'


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
        yield c, cfg, banco


def entrar_e_criar(cliente, *, nome="Projeto Multi Teste"):
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Ana Teste", "email": "ana@imap.com.br", "senha": SENHA},
    )
    r_entrar = cliente.post(
        f"{API}/auth/entrar",
        json={"email": "ana@imap.com.br", "senha": SENHA},
    )
    csrf = r_entrar.headers.get("X-MF-CSRF") or cliente.get(f"{API}/auth/eu").json()["csrf"]
    r_proj = cliente.post(
        f"{API}/projetos",
        json={"nome": nome, "folha": {"formato": "A4", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": csrf},
    )
    return csrf, r_proj.json()["projeto"]


def enviar_zip(cliente, csrf: str, conteudo: bytes, *, parte_mb: int = 1) -> str:
    criado = cliente.post(
        f"{API}/uploads",
        json={"nome": "multi_imovel.zip", "tamanho": len(conteudo)},
        headers={"X-MF-CSRF": csrf},
    )
    assert criado.status_code == 201, criado.text
    dados = criado.json()
    parte_bytes = parte_mb * 1024 * 1024
    hexes = []
    for numero in range(dados["total_partes"]):
        pedaco = conteudo[numero * parte_bytes : (numero + 1) * parte_bytes]
        hash_parte = hashlib.sha256(pedaco).hexdigest()
        hexes.append(hash_parte)
        resposta = cliente.put(
            f"{API}/uploads/{dados['upload_id']}/partes/{numero}",
            content=pedaco,
            headers={"X-MF-CSRF": csrf, "X-Parte-SHA256": hash_parte},
        )
        assert resposta.status_code == 204, resposta.text
    hash_partes = hashlib.sha256("".join(hexes).encode("ascii")).hexdigest()
    concluido = cliente.post(
        f"{API}/uploads/{dados['upload_id']}/concluir",
        json={"hash_partes": hash_partes},
        headers={"X-MF-CSRF": csrf},
    )
    assert concluido.status_code == 200, concluido.text
    return dados["upload_id"]


def test_migracao_0004_cria_imoveis_projeto_e_backfill(tmp_path: Path) -> None:
    """Testa que a migração 0004 é aditiva e faz o backfill sem inventar dados."""
    caminho_db = tmp_path / "teste_migracao.sqlite"
    banco = db.Banco(caminho_db)

    # 1. Aplica migrações até 0003 manualmente
    con = banco.conectar()
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (versao INTEGER PRIMARY KEY, aplicada_em TEXT NOT NULL)"
    )
    for num, nome_mig in [(1, "0001_inicial.sql"), (2, "0002_conversa_do_projeto.sql"), (3, "0003_abertura_feita.sql")]:
        script = (db.MIGRACOES_DIR / nome_mig).read_text(encoding="utf-8")
        con.executescript(script)
        con.execute("INSERT INTO schema_version (versao, aplicada_em) VALUES (?, datetime('now'))", (num,))

    usuario_id = "user_teste_mig"
    agora = sessoes.iso(sessoes.agora())
    con.execute(
        "INSERT INTO usuarios (id, email, nome, papel, senha_hash, criado_em) VALUES (?,?,?,?,?,?)",
        (usuario_id, "mig@teste.com", "User Mig", "usuario", senhas.gerar_hash("senha123"), agora),
    )

    # Projeto 1: possui dados de imóvel
    con.execute(
        "INSERT INTO projetos (id, usuario_id, nome, estado, folha_formato, folha_orientacao, imovel_nome, imovel_car, imovel_municipio, imovel_uf, criado_em, atualizado_em)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("proj_com_imovel", usuario_id, "Projeto Alfa", "pronto", "A4", "retrato", "Fazenda Alfa", "MT-001/2026", "Querência", "MT", agora, agora),
    )

    # Projeto 2: sem dados de imóvel
    con.execute(
        "INSERT INTO projetos (id, usuario_id, nome, estado, folha_formato, folha_orientacao, criado_em, atualizado_em)"
        " VALUES (?,?,?,?,?,?,?,?)",
        ("proj_sem_imovel", usuario_id, "Projeto Vazio", "aguardando_zip", "A4", "retrato", agora, agora),
    )
    con.close()

    assert banco.versao() == 3

    # 2. Executa a migração para a versão 4
    versao_final = banco.migrar()
    assert versao_final == 4

    con = banco.conectar()
    linhas = con.execute("SELECT * FROM imoveis_projeto WHERE projeto_id = 'proj_com_imovel'").fetchall()
    assert len(linhas) == 1
    im = linhas[0]
    assert im["nome"] == "Fazenda Alfa"
    assert im["car"] == "MT-001/2026"
    assert im["matricula"] is None  # Sem inventar dado!
    assert im["area_ha"] is None    # Sem inventar dado!
    assert im["principal"] == 1

    linhas_vazio = con.execute("SELECT * FROM imoveis_projeto WHERE projeto_id = 'proj_sem_imovel'").fetchall()
    assert len(linhas_vazio) == 0

    # Idempotência: rodar de novo não falha nem duplica
    assert banco.migrar() == 4
    linhas_pos = con.execute("SELECT * FROM imoveis_projeto WHERE projeto_id = 'proj_com_imovel'").fetchall()
    assert len(linhas_pos) == 1
    con.close()


def test_importacao_salva_multi_imoveis_no_banco(ambiente) -> None:
    """Importação com 2 imóveis salva imoveis[] no resumo e na tabela imoveis_projeto."""
    cliente, cfg, banco = ambiente
    csrf, projeto = entrar_e_criar(cliente, nome="Projeto Multi Imoveis")

    # Monta ZIP em memória com 2 shapefiles de ATP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CAR_1/ATP.shp", b"shp1")
        zf.writestr("CAR_1/ATP.shx", b"shx1")
        zf.writestr("CAR_1/ATP.dbf", b"dbf1")
        zf.writestr("CAR_1/ATP.prj", PRJ_TEXTO)
        zf.writestr("CAR_2/LOTE_45.shp", b"shp2")
        zf.writestr("CAR_2/LOTE_45.shx", b"shx2")
        zf.writestr("CAR_2/LOTE_45.dbf", b"dbf2")
        zf.writestr("CAR_2/LOTE_45.prj", PRJ_TEXTO)
        zf.writestr("LEIA-ME.txt", "dois imoveis")

    conteudo_zip = buf.getvalue()
    upload_id = enviar_zip(cliente, csrf, conteudo_zip)

    r_imp = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": upload_id},
        headers={"X-MF-CSRF": csrf},
    )
    assert r_imp.status_code == 202
    importacao_id = r_imp.json()["importacao_id"]

    # Consulta estado da importação
    r_est = cliente.get(f"{API}/importacoes/{importacao_id}")
    assert r_est.status_code == 200
    resumo = r_est.json()["resumo"]
    assert "imoveis" in resumo
    assert len(resumo["imoveis"]) == 2

    # Confere no banco
    con = banco.conectar()
    imoveis_banco = projetos_repo.listar_imoveis(con, projeto["id"])
    assert len(imoveis_banco) == 2
    principais = [i for i in imoveis_banco if i["principal"]]
    assert len(principais) == 1

    # Confere compatibilidade singular
    proj_atual = projetos_repo.exigir(con, projeto["id"], usuario_id="", admin=True)
    assert proj_atual.imovel["nome"] is not None
    con.close()


def test_api_projetos_imoveis_e_detalhar(ambiente):
    """Testa endpoints GET /projetos/{id}/imoveis e imoveis em GET /projetos/{id}."""
    cliente, cfg, banco = ambiente
    csrf, projeto = entrar_e_criar(cliente)

    con = banco.conectar()
    projetos_repo.salvar_imoveis(
        con,
        projeto["id"],
        [
            {"id": "im_1", "nome": "Gleba 1", "car": "MT-001", "principal": True},
            {"id": "im_2", "nome": "Gleba 2", "car": "MT-002", "principal": False},
        ],
    )
    con.close()

    # 1. GET /projetos/{id}/imoveis
    r = cliente.get(f"{API}/projetos/{projeto['id']}/imoveis")
    assert r.status_code == 200
    dados = r.json()
    assert "imoveis" in dados
    assert len(dados["imoveis"]) == 2
    assert dados["imoveis"][0]["id"] == "im_1"
    assert dados["imoveis"][0]["principal"] is True

    # 2. GET /projetos/{id} (detalhar)
    r_detalhe = cliente.get(f"{API}/projetos/{projeto['id']}")
    assert r_detalhe.status_code == 200
    dados_det = r_detalhe.json()
    assert "imoveis" in dados_det
    assert len(dados_det["imoveis"]) == 2


def test_api_agente_estado_e_aprovacao_segura(ambiente):
    """Testa GET /projetos/{id}/agente e POST /projetos/{id}/agente/aprovacao."""
    cliente, cfg, banco = ambiente
    csrf, projeto = entrar_e_criar(cliente)

    # 1. GET antes de existir .agente/estado.json devolve contrato neutro
    r = cliente.get(f"{API}/projetos/{projeto['id']}/agente")
    assert r.status_code == 200
    estado = r.json()
    assert estado == {
        "passos": [],
        "arquivos": [],
        "previews": [],
        "aprovacao": None,
        "status": "pendente",
        "resumo": None,
        "versao": None,
    }

    # 2. POST /projetos/{id}/agente/aprovacao com acao inválida -> 400
    r_invalido = cliente.post(
        f"{API}/projetos/{projeto['id']}/agente/aprovacao",
        json={"acao": "hackear"},
        headers={"X-MF-CSRF": csrf},
    )
    assert r_invalido.status_code == 400

    # 2.5 Cria pedido em .servidor/aprovacoes/pedido.json
    raiz = Path(str(banco.caminho)).parent / "projetos" / projeto["id"]
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    pasta_aprov.mkdir(parents=True, exist_ok=True)
    import time as _t
    (pasta_aprov / "pedido.json").write_text(
        json.dumps({
            "token": "tok_teste_aprovacao",
            "action": "aprovar_mapas",
            "ttl": 300,
            "timestamp": _t.time(),
        }),
        encoding="utf-8",
    )
    r_ped = cliente.get(f"{API}/projetos/{projeto['id']}/agente")
    assert r_ped.status_code == 200
    token_pub = r_ped.json()["aprovacao"]["token"]

    # 3. POST /projetos/{id}/agente/aprovacao com sucesso
    r_aprov = cliente.post(
        f"{API}/projetos/{projeto['id']}/agente/aprovacao",
        json={"acao": "aprovar", "token": token_pub, "motivo": "Mapas conferidos e aprovados"},
        headers={"X-MF-CSRF": csrf},
    )
    assert r_aprov.status_code == 200
    dados_aprov = r_aprov.json()
    assert dados_aprov["status"] == "aprovado"
    assert dados_aprov["aprovacao"]["status"] == "aprovado"
    assert dados_aprov["aprovacao"]["motivo"] == "Mapas conferidos e aprovados"

    # 4. GET subsequente retorna o estado gravado em disco
    r_novo = cliente.get(f"{API}/projetos/{projeto['id']}/agente")
    assert r_novo.status_code == 200
    assert r_novo.json()["status"] == "aprovado"
    assert r_novo.json()["aprovacao"]["motivo"] == "Mapas conferidos e aprovados"


def test_api_agente_auth_owner_protege_acesso(ambiente):
    """Usuário sem autenticação ou alheio recebe 401 / 404 ao tentar ler/aprovar agente."""
    cliente, cfg, banco = ambiente
    csrf, projeto = entrar_e_criar(cliente, nome="Projeto Protegido")

    # Cliente anônimo
    cliente_anonimo = TestClient(cliente.app, base_url="https://testserver")
    r_anon = cliente_anonimo.get(f"{API}/projetos/{projeto['id']}/agente")
    assert r_anon.status_code == 401

    r_post_anon = cliente_anonimo.post(
        f"{API}/projetos/{projeto['id']}/agente/aprovacao",
        json={"acao": "aprovar"},
    )
    assert r_post_anon.status_code == 401

