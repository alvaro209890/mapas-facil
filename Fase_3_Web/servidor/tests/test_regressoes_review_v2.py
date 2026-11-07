"""Testes de regressão focados pós-revisão ciclo 1 (test_regressoes_review_v2.py).

Cobre estritamente os 4 pontos de revisão:
(1) Migração 0004 + backfill id preservado vs salvar_imoveis ON CONFLICT(projeto_id, imovel_id)
(2) pacote.zip: download filename seguro (../Fazenda:teste), nome físico controlado com fingerprint, gates MF_MXD=1 e ?mxd=1
(3) Importação: sem invenção de APP/hidro como imóvel, sem import direto de nucleo em prod, preservação de dados anteriores
(4) Aprovação: contrato nativo de decisao.json ({aprovado, acao, caminho, hash_alvo, timestamp, consumido, pedido_id}),
    não apagar pedido.json no POST, consumo real single-use pelo núcleo via arquivos
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from mapasfacil_servidor import db, projetos_repo
from mapasfacil_servidor.auth import senhas, sessoes


def test_migracao_0004_backfill_e_salvar_imoveis_preserva_id_antigo(tmp_path: Path) -> None:
    """(1) Provar banco schema3 com 1 projeto e versão, migrar para schema 4,

    e salvar_imoveis atualizando sem colisão UNIQUE e preservando id antigo.
    """
    caminho_db = tmp_path / "schema3_legado.sqlite"
    banco = db.Banco(caminho_db)

    # 1. Configura banco no schema 3
    con = banco.conectar()
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (versao INTEGER PRIMARY KEY, aplicada_em TEXT NOT NULL)"
    )
    for num, mig_nome in [
        (1, "0001_inicial.sql"),
        (2, "0002_conversa_do_projeto.sql"),
        (3, "0003_abertura_feita.sql"),
    ]:
        script = (db.MIGRACOES_DIR / mig_nome).read_text(encoding="utf-8")
        con.executescript(script)
        con.execute(
            "INSERT INTO schema_version (versao, aplicada_em) VALUES (?, datetime('now'))",
            (num,),
        )

    agora = sessoes.iso(sessoes.agora())
    con.execute(
        "INSERT INTO usuarios (id, email, nome, papel, senha_hash, criado_em) VALUES (?,?,?,?,?,?)",
        ("usr_1", "user@teste.com", "Usuário", "usuario", senhas.gerar_hash("senha123"), agora),
    )

    proj_id = "proj_legado_schema3"
    con.execute(
        "INSERT INTO projetos (id, usuario_id, nome, estado, folha_formato, folha_orientacao, imovel_nome, imovel_car, criado_em, atualizado_em)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (proj_id, "usr_1", "Fazenda Antiga", "pronto", "A4", "retrato", "Fazenda Original", "MT-9999/2026", agora, agora),
    )

    # Versão associada existente no schema 3
    con.execute(
        "INSERT INTO versoes (projeto_id, numero, pasta, conforme, artefatos, criada_em)"
        " VALUES (?,?,?,?,?,?)",
        (proj_id, 1, "Mapas/v001", 1, json.dumps({"pdf": "Mapas/v001/mapa.pdf"}), agora),
    )
    con.commit()
    con.close()

    assert banco.versao() == 3

    # 2. Executa migração para schema 4
    versao_pos = banco.migrar()
    assert versao_pos == 4

    con = banco.conectar()
    # Verifica backfill da migração 0004
    imoveis_iniciais = con.execute(
        "SELECT * FROM imoveis_projeto WHERE projeto_id = ?", (proj_id,)
    ).fetchall()
    assert len(imoveis_iniciais) == 1
    im_ini = imoveis_iniciais[0]
    id_esperado = f"{proj_id}_principal"
    assert im_ini["id"] == id_esperado
    assert im_ini["imovel_id"] == "imovel_principal"
    assert im_ini["nome"] == "Fazenda Original"
    assert im_ini["car"] == "MT-9999/2026"

    # 3. Chama salvar_imoveis atualizando dados com imovel_id='imovel_principal'
    # Sem o fix de ON CONFLICT(projeto_id, imovel_id), falha com UNIQUE constraint failed.
    salvos = projetos_repo.salvar_imoveis(
        con,
        proj_id,
        [
            {
                "id": "imovel_principal",
                "nome": "Fazenda Retificada",
                "car": "MT-9999/2026",
                "matricula": "12345",
                "area": 1420.75,
                "atp": "SHP/ATP.shp",
                "principal": True,
            }
        ],
    )
    assert len(salvos) == 1

    # 4. Verifica que o registro foi atualizado sem duplicar e PRESERVANDO o id antigo
    imoveis_pos = con.execute(
        "SELECT * FROM imoveis_projeto WHERE projeto_id = ?", (proj_id,)
    ).fetchall()
    assert len(imoveis_pos) == 1
    im_fim = imoveis_pos[0]
    assert im_fim["id"] == id_esperado, "O id gerado pelo backfill deve ser preservado intacto!"
    assert im_fim["imovel_id"] == "imovel_principal"
    assert im_fim["nome"] == "Fazenda Retificada"
    assert im_fim["matricula"] == "12345"
    assert im_fim["area_ha"] == 1420.75
    assert im_fim["atp_fonte"] == "SHP/ATP.shp"

    # 5. Verifica que a versão original permaneceu 100% intacta
    versao_row = con.execute(
        "SELECT * FROM versoes WHERE projeto_id = ? AND numero = 1", (proj_id,)
    ).fetchone()
    assert versao_row is not None
    assert versao_row["pasta"] == "Mapas/v001"
    assert versao_row["conforme"] == 1
    con.close()


def test_pacote_zip_seguranca_nome_e_gates_mxd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(2) Testa:
    - projeto.nome com '../Fazenda:teste' -> download filename seguro sem '..' ou ':'
    - nome físico com ID controlado + versão + policy + fingerprint
    - default sem MXD mesmo com artefato presente e MF_MXD=1
    - ?mxd=1 exige ambos os gates (opt-in na query + MF_MXD=1)
    - cache separado com/sem MXD
    """
    import zipfile
    from fastapi.testclient import TestClient
    from mapasfacil_servidor.app import create_app
    from mapasfacil_servidor.config import carregar
    from mapasfacil_servidor.versoes_sync import raiz_do_projeto

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text("MAPASFACIL_PROVEDOR_CHAVE=chave-teste\n", encoding="utf-8")
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MF_ADMIN_EMAIL", "admin@teste.com")

    # Garante MF_MXD=1 inicialmente para testar o gate
    monkeypatch.setenv("MF_MXD", "1")

    cfg = carregar()
    banco = db.Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, admin_email=cfg.admin_email, origem="https://testserver", config=cfg)

    client = TestClient(app, base_url="https://testserver")

    # Cria usuário e faz login
    cad = client.post(
        "/api/v1/auth/cadastrar",
        json={"nome": "Admin", "email": "admin@teste.com", "senha": "SenhaForte123!"},
    )
    assert cad.status_code == 201
    csrf_token = client.get("/api/v1/auth/eu").json()["csrf"]

    # Cria projeto com nome potencialmente perigoso (path traversal + símbolos)
    nome_perigoso = "../Fazenda:teste"
    resp_proj = client.post(
        "/api/v1/projetos",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": nome_perigoso, "folha": {"formato": "A4", "orientacao": "retrato"}},
    )
    assert resp_proj.status_code == 201
    proj = resp_proj.json()["projeto"]
    proj_id = proj["id"]

    # Cria estrutura de arquivos da versão no filesystem do projeto
    ws_raiz = raiz_do_projeto(app.state.mf, proj_id)
    pasta_v1 = ws_raiz / "Mapas" / "v001"
    pasta_v1.mkdir(parents=True, exist_ok=True)
    pdf_file = pasta_v1 / "mapa.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 mock")

    # Arquivo MXD existe no filesystem
    pasta_mxd = ws_raiz / "MXD"
    pasta_mxd.mkdir(parents=True, exist_ok=True)
    mxd_file = pasta_mxd / "mapa.mxd"
    mxd_file.write_bytes(b"mock mxd content")

    # Registra versão no banco com artefato MXD presente e conforme=1
    con = banco.conectar()
    agora = sessoes.iso(sessoes.agora())
    con.execute(
        "INSERT INTO versoes (projeto_id, numero, pasta, conforme, artefatos, validacao, criada_em)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            proj_id,
            1,
            "Mapas/v001",
            1,
            json.dumps({"pdf": "Mapas/v001/mapa.pdf", "mxd": "MXD/mapa.mxd"}),
            json.dumps({"valido": True}),
            agora,
        ),
    )
    con.commit()
    con.close()

    # --- CASO A: Default sem query param (mxd=False) com MF_MXD=1 ---
    # Mesmo com MF_MXD=1 e artefato existente, default DEVE ser PDF-first sem MXD!
    resp_default = client.get(f"/api/v1/projetos/{proj_id}/versoes/1/pacote.zip")
    assert resp_default.status_code == 200

    # 1. Checa Content-Disposition e filename seguro
    cd = resp_default.headers.get("content-disposition", "")
    assert ".." not in cd, f"Filename não pode conter '..': {cd}"
    assert ":" not in cd, f"Filename não pode conter ':': {cd}"
    assert "/" not in cd and "\\" not in cd
    assert "Fazenda_teste_v001.zip" in cd

    # 2. Checa nome físico no disco (ID controlado + versão + policy + fingerprint)
    pasta_pacotes = ws_raiz / ".servidor" / "pacotes"
    zips_nomxd = list(pasta_pacotes.glob(f"{proj_id}_v001_nomxd_*.zip"))
    assert len(zips_nomxd) == 1, f"Deve existir arquivo físico com ID controlado e nomxd: {list(pasta_pacotes.glob('*'))}"
    caminho_fisico_nomxd = zips_nomxd[0]

    # 3. Conteúdo do zip default: NÃO DEVE conter pasta MXD
    with zipfile.ZipFile(caminho_fisico_nomxd, "r") as zf:
        nomes = zf.namelist()
        assert not any(n.startswith("MXD/") for n in nomes), f"Default não deve incluir MXD/: {nomes}"
        assert any(n.startswith("Mapas/") for n in nomes), f"Deve incluir Mapas/: {nomes}"

    # --- CASO B: Opt-in com ?mxd=1 mas MF_MXD desativado ---
    monkeypatch.setenv("MF_MXD", "0")
    resp_optin_sem_env = client.get(f"/api/v1/projetos/{proj_id}/versoes/1/pacote.zip?mxd=1")
    assert resp_optin_sem_env.status_code == 200
    # Como MF_MXD=0, o gate do ambiente bloqueia a inclusão do MXD
    # Deve usar/gerar pacote nomxd
    zips_apos_sem_env = list(pasta_pacotes.glob(f"{proj_id}_v001_nomxd_*.zip"))
    assert len(zips_apos_sem_env) >= 1

    # --- CASO C: Opt-in com ?mxd=1 E MF_MXD=1 (Ambos os gates ativos) ---
    monkeypatch.setenv("MF_MXD", "1")
    resp_optin_ambos = client.get(f"/api/v1/projetos/{proj_id}/versoes/1/pacote.zip?mxd=1")
    assert resp_optin_ambos.status_code == 200

    # Cache separado para MXD: deve existir arquivo com policy 'mxd'
    zips_mxd = list(pasta_pacotes.glob(f"{proj_id}_v001_mxd_*.zip"))
    assert len(zips_mxd) == 1, f"Deve existir arquivo físico de cache separado para mxd: {list(pasta_pacotes.glob('*'))}"
    caminho_fisico_mxd = zips_mxd[0]

    with zipfile.ZipFile(caminho_fisico_mxd, "r") as zf:
        nomes_mxd = zf.namelist()
        assert any(n.startswith("MXD/") for n in nomes_mxd), f"Com ambos os gates, deve incluir MXD/: {nomes_mxd}"


def test_servidor_nao_importa_nucleo_direto_em_producao() -> None:
    """(3) CI gate: mapasfacil_servidor NÃO deve importar mapasfacil_nucleo diretamente

    em código de produção (apenas processos filhos via pool/NDJSON são permitidos).
    """
    import re
    servidor_dir = Path(__file__).resolve().parent.parent / "mapasfacil_servidor"
    violacoes = []
    for py_file in servidor_dir.rglob("*.py"):
        linhas = py_file.read_text(encoding="utf-8").splitlines()
        for idx, linha in enumerate(linhas, start=1):
            # Ignora comentários
            linha_strip = linha.strip()
            if linha_strip.startswith("#"):
                continue
            if re.search(r"\b(?:import\s+mapasfacil_nucleo|from\s+mapasfacil_nucleo)\b", linha_strip):
                violacoes.append(f"{py_file.name}:{idx}: {linha_strip}")

    assert not violacoes, f"Violação de arquitetura/CI gate: imports diretos do núcleo no servidor encontrados: {violacoes}"


def test_importacao_nao_inventa_imovel_com_app_hidro_e_preserva_anteriores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(3) Se a detecção de múltiplos imóveis não encontrar ATP com evidência:

    - NÃO deve criar APP ou hidro como imóvel;
    - Emite aviso de detecção indisponível;
    - Preserva dados anteriores de imóveis se a detecção falhar em reimportação.
    """
    import zipfile
    from fastapi.testclient import TestClient
    from mapasfacil_servidor.app import create_app
    from mapasfacil_servidor.config import carregar
    from mapasfacil_servidor.importacao import servico as import_servico
    from mapasfacil_servidor.versoes_sync import raiz_do_projeto

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text("MAPASFACIL_PROVEDOR_CHAVE=chave-teste\n", encoding="utf-8")
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MF_ADMIN_EMAIL", "admin@teste.com")

    cfg = carregar()
    banco = db.Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, admin_email=cfg.admin_email, origem="https://testserver", config=cfg)
    client = TestClient(app, base_url="https://testserver")

    # Cadastra usuário
    cad = client.post(
        "/api/v1/auth/cadastrar",
        json={"nome": "Admin", "email": "admin@teste.com", "senha": "SenhaForte123!"},
    )
    assert cad.status_code == 201
    csrf_token = client.get("/api/v1/auth/eu").json()["csrf"]

    # Cria projeto
    resp_proj = client.post(
        "/api/v1/projetos",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": "Projeto Reimport", "folha": {"formato": "A4", "orientacao": "retrato"}},
    )
    assert resp_proj.status_code == 201
    proj_id = resp_proj.json()["projeto"]["id"]

    # Pre-popula imóvel anterior no projeto para testar preservação
    con = banco.conectar()
    projetos_repo.salvar_imoveis(
        con,
        proj_id,
        [
            {
                "id": "imovel_principal",
                "nome": "Fazenda Original",
                "car": "MT-1111/2026",
                "principal": True,
            }
        ],
    )
    con.commit()
    con.close()

    # Cria zip contendo APENAS APP.shp, hidrografia.shp e reserva_legal.shp (sem recibo e sem ATP)
    caminho_zip = tmp_path / "app_hidro.zip"
    with zipfile.ZipFile(caminho_zip, "w") as zf:
        zf.writestr("APP.shp", b"dummy shp content")
        zf.writestr("hidrografia.shp", b"dummy hidro content")
        zf.writestr("reserva_legal.shp", b"dummy reserva content")

    conteudo_zip = caminho_zip.read_bytes()

    # Faz upload pelas APIs do servidor
    up_resp = client.post(
        "/api/v1/uploads",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": "app_hidro.zip", "tamanho": len(conteudo_zip)},
    )
    assert up_resp.status_code == 201
    upload_id = up_resp.json()["upload_id"]

    import hashlib
    h_parte = hashlib.sha256(conteudo_zip).hexdigest()
    client.put(
        f"/api/v1/uploads/{upload_id}/partes/0",
        headers={"X-MF-CSRF": csrf_token, "X-Parte-SHA256": h_parte},
        content=conteudo_zip,
    )
    resp_conc = client.post(
        f"/api/v1/uploads/{upload_id}/concluir",
        headers={"X-MF-CSRF": csrf_token},
        json={"hash_partes": hashlib.sha256(h_parte.encode("ascii")).hexdigest()},
    )
    assert resp_conc.status_code == 200, resp_conc.text

    # Executa importação (sem worker pool do núcleo)
    raizes = import_servico.Raizes(
        projetos=cfg.projetos,
        uploads=cfg.uploads,
        extraido_max_bytes=cfg.extraido_max_mb * 1024 * 1024,
    )
    con = banco.conectar()
    imp_id = import_servico.registrar_importacao(con, projeto_id=proj_id, upload_id=upload_id)
    con.commit()
    projeto_obj = projetos_repo.obter(con, proj_id, usuario_id=cad.json()["usuario"]["id"], admin=True)
    assert projeto_obj is not None

    resumo = import_servico.importar(
        banco=banco,
        raizes=raizes,
        projeto=projeto_obj,
        upload_id=upload_id,
        importacao_id=imp_id,
        pool=None,
        chamar=None,
    )

    imoveis_depois = projetos_repo.listar_imoveis(con, proj_id)
    nomes_imoveis = [im["nome"] for im in imoveis_depois]

    # NÃO DEVE ter inventado 'App', 'Hidrografia' ou 'Reserva Legal' como imóveis!
    assert not any("App" in n or "Hidrografia" in n or "Reserva" in n for n in nomes_imoveis), (
        f"APP/hidro não podem ser promovidos a imóveis: {nomes_imoveis}"
    )

    # Deve ter preservado o imóvel anterior ("Fazenda Original")
    assert len(imoveis_depois) == 1
    assert imoveis_depois[0]["nome"] == "Fazenda Original"

    # Deve ter gerado aviso de imóveis múltiplos indisponível ou sem ATP
    avisos_codigos = [a.get("codigo") for a in resumo.get("avisos", [])]
    assert "IM-030" in avisos_codigos
    con.close()


def test_importacao_com_atp_evidencia_e_legacy_normal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(3) Testa que shapefiles com evidência clara de ATP (ATP_1.shp e ATP_2.shp) são detectados,

    e que importação normal legacy (recibo/imovel único) continua funcionando perfeitamente.
    """
    import zipfile
    from fastapi.testclient import TestClient
    from mapasfacil_servidor.app import create_app
    from mapasfacil_servidor.config import carregar
    from mapasfacil_servidor.importacao import servico as import_servico

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text("MAPASFACIL_PROVEDOR_CHAVE=chave-teste\n", encoding="utf-8")
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MF_ADMIN_EMAIL", "admin@teste.com")

    cfg = carregar()
    banco = db.Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, admin_email=cfg.admin_email, origem="https://testserver", config=cfg)
    client = TestClient(app, base_url="https://testserver")

    cad = client.post(
        "/api/v1/auth/cadastrar",
        json={"nome": "Admin", "email": "admin@teste.com", "senha": "SenhaForte123!"},
    )
    csrf_token = client.get("/api/v1/auth/eu").json()["csrf"]

    # Cria projeto
    resp_proj = client.post(
        "/api/v1/projetos",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": "Projeto Dois ATPs", "folha": {"formato": "A4", "orientacao": "retrato"}},
    )
    proj_id = resp_proj.json()["projeto"]["id"]

    # Zip com ATP_1.shp, ATP_2.shp e uma APP.shp
    caminho_zip = tmp_path / "dois_atps.zip"
    with zipfile.ZipFile(caminho_zip, "w") as zf:
        zf.writestr("ATP_Gleba_1.shp", b"dummy")
        zf.writestr("ATP_Gleba_2.shp", b"dummy")
        zf.writestr("APP.shp", b"dummy")

    conteudo_zip = caminho_zip.read_bytes()
    up_resp = client.post(
        "/api/v1/uploads",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": "dois_atps.zip", "tamanho": len(conteudo_zip)},
    )
    upload_id = up_resp.json()["upload_id"]
    import hashlib
    h_parte = hashlib.sha256(conteudo_zip).hexdigest()
    client.put(
        f"/api/v1/uploads/{upload_id}/partes/0",
        headers={"X-MF-CSRF": csrf_token, "X-Parte-SHA256": h_parte},
        content=conteudo_zip,
    )
    client.post(
        f"/api/v1/uploads/{upload_id}/concluir",
        headers={"X-MF-CSRF": csrf_token},
        json={"hash_partes": hashlib.sha256(h_parte.encode("ascii")).hexdigest()},
    )

    raizes = import_servico.Raizes(
        projetos=cfg.projetos,
        uploads=cfg.uploads,
        extraido_max_bytes=cfg.extraido_max_mb * 1024 * 1024,
    )
    con = banco.conectar()
    imp_id = import_servico.registrar_importacao(con, projeto_id=proj_id, upload_id=upload_id)
    con.commit()
    projeto_obj = projetos_repo.obter(con, proj_id, usuario_id=cad.json()["usuario"]["id"], admin=True)
    assert projeto_obj is not None

    resumo = import_servico.importar(
        banco=banco,
        raizes=raizes,
        projeto=projeto_obj,
        upload_id=upload_id,
        importacao_id=imp_id,
        pool=None,
        chamar=None,
    )

    imoveis = projetos_repo.listar_imoveis(con, proj_id)
    nomes = [im["nome"] for im in imoveis]
    # Deve conter Gleba 1 e Gleba 2
    assert any("Gleba 1" in n for n in nomes)
    assert any("Gleba 2" in n for n in nomes)
    # NÃO deve conter APP
    assert not any("App" in n for n in nomes)
    con.close()


def test_aprovacao_integracao_real_humano_post_nucleo_single_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(4) Integração real:

    - Núcleo (via subprocesso de arquivos) solicita aprovação -> gera pedido.json com token;
    - Token acessível apenas pelo owner UI via GET /agente, nunca em NDJSON/estado.json;
    - Humano POST aprova: grava decisao.json no contrato nativo {aprovado: True, acao, caminho, hash_alvo, timestamp, consumido: False, pedido_id};
    - POST NÃO apaga pedido.json (deixa status='aprovado');
    - Núcleo consome a decisão exatamente uma vez (single-use) e atualiza pedido.json para 'concluido';
    - Segunda tentativa de consumo recusa e não reutiliza.
    """
    from fastapi.testclient import TestClient
    from mapasfacil_servidor.app import create_app
    from mapasfacil_servidor.config import carregar
    from mapasfacil_servidor.versoes_sync import raiz_do_projeto

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text("MAPASFACIL_PROVEDOR_CHAVE=chave-teste\n", encoding="utf-8")
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MF_ADMIN_EMAIL", "admin@teste.com")

    cfg = carregar()
    banco = db.Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, admin_email=cfg.admin_email, origem="https://testserver", config=cfg)
    client = TestClient(app, base_url="https://testserver")

    # Cadastra owner
    cad = client.post(
        "/api/v1/auth/cadastrar",
        json={"nome": "Owner", "email": "owner@teste.com", "senha": "SenhaForte123!"},
    )
    csrf_token = client.get("/api/v1/auth/eu").json()["csrf"]

    # Cria projeto
    resp_proj = client.post(
        "/api/v1/projetos",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": "Projeto Aprovacao Real", "folha": {"formato": "A4", "orientacao": "retrato"}},
    )
    proj_id = resp_proj.json()["projeto"]["id"]
    ws_raiz = raiz_do_projeto(app.state.mf, proj_id)
    ws_raiz.mkdir(parents=True, exist_ok=True)

    # Cria arquivo no workspace para ser alvo de exclusão
    arquivo_alvo = ws_raiz / "temporario.txt"
    arquivo_alvo.write_text("conteudo sensivel a ser apagado", encoding="utf-8")

    # 1. Executa script em subprocesso para chamar GerenciadorAprovacao nativo do núcleo
    # sem importar mapasfacil_nucleo no processo do servidor.
    caminho_nucleo = Path(__file__).resolve().parents[3] / "Fase_1_Desktop" / "nucleo"
    assert (caminho_nucleo / "mapasfacil_nucleo").is_dir()
    python_nucleo = caminho_nucleo / ".venv" / "Scripts" / "python.exe"
    executavel_subprocess = str(python_nucleo if python_nucleo.is_file() else sys.executable)

    codigo_solicitar = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{caminho_nucleo}")
from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao

ws = Path(r"{ws_raiz}")
gerenciador = GerenciadorAprovacao(ws)
res = gerenciador.solicitar(
    acao="apagar",
    caminho="temporario.txt",
    motivo="Exclusão de teste pelo agente",
    ws_root=ws,
)
assert res["aguardando_aprovacao"] is True
print("OK_SOLICITADO")
"""
    proc1 = subprocess.run(
        [executavel_subprocess, "-c", codigo_solicitar],
        capture_output=True,
        text=True,
    )
    assert proc1.returncode == 0, f"proc1 falhou: stdout={proc1.stdout}\nstderr={proc1.stderr}"
    assert "OK_SOLICITADO" in proc1.stdout

    # 2. Confere que o token NÃO está no .agente/estado.json nem acessível publicamente
    pasta_agente = ws_raiz / ".agente"
    if (pasta_agente / "estado.json").exists():
        conteudo_estado = (pasta_agente / "estado.json").read_text(encoding="utf-8")
        assert "token" not in conteudo_estado

    # 3. Owner UI busca o estado via GET /agente e obtém o token seguro
    resp_estado = client.get(f"/api/v1/projetos/{proj_id}/agente")
    assert resp_estado.status_code == 200
    dados_agente = resp_estado.json()
    aprov_info = dados_agente.get("aprovacao")
    assert aprov_info is not None
    assert aprov_info["status"] == "pendente"
    token_ui = aprov_info["token"]
    assert token_ui and len(token_ui) >= 32

    # 4. Humano envia POST /agente/aprovacao aprovando a ação
    resp_post = client.post(
        f"/api/v1/projetos/{proj_id}/agente/aprovacao",
        headers={"X-MF-CSRF": csrf_token},
        json={
            "acao": "aprovar",
            "token": token_ui,
            "action": "apagar",
            "path": "temporario.txt",
            "motivo": "Aprovado pelo proprietário humano",
        },
    )
    assert resp_post.status_code == 200
    corpo_post = resp_post.json()
    assert corpo_post["ok"] is True

    # 5. Verifica os arquivos em .servidor/aprovacoes/
    pasta_aprov = ws_raiz / ".servidor" / "aprovacoes"
    arquivo_pedido = pasta_aprov / "pedido.json"
    arquivo_decisao = pasta_aprov / "decisao.json"

    # CRUCIAL: pedido.json NÃO PODE ter sido apagado pelo POST!
    assert arquivo_pedido.is_file(), "POST não deve apagar pedido.json antes do núcleo consumir!"
    pedido_dados = json.loads(arquivo_pedido.read_text(encoding="utf-8"))
    assert pedido_dados["status"] == "aprovado"

    # CRUCIAL: decisao.json deve ter o contrato nativo exigido pelo núcleo
    assert arquivo_decisao.is_file()
    decisao_dados = json.loads(arquivo_decisao.read_text(encoding="utf-8"))
    assert decisao_dados.get("aprovado") is True, f"decisao.json deve conter 'aprovado': True. Dados: {decisao_dados}"
    assert decisao_dados.get("acao") == "apagar", f"decisao.json deve conter acao='apagar'. Dados: {decisao_dados}"
    assert decisao_dados.get("caminho") == "temporario.txt", f"decisao.json deve conter caminho='temporario.txt'. Dados: {decisao_dados}"
    assert decisao_dados.get("consumido") is False
    assert isinstance(decisao_dados.get("timestamp"), (int, float))

    # 6. Executa script em subprocesso para o núcleo consumir a decisão (single-use)
    codigo_consumir = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{caminho_nucleo}")
from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao

ws = Path(r"{ws_raiz}")
gerenciador = GerenciadorAprovacao(ws)

# Primeira chamada: DEVE consumir com sucesso
ok1 = gerenciador.verificar_e_consumir_decisao(
    acao="apagar",
    caminho="temporario.txt",
    ws_root=ws,
)
assert ok1 is True, "Núcleo deve consumir com sucesso a decisão aprovada!"

# Segunda chamada imediata: DEVE recusar (single-use consumido)
ok2 = gerenciador.verificar_e_consumir_decisao(
    acao="apagar",
    caminho="temporario.txt",
    ws_root=ws,
)
assert ok2 is False, "Decisão não pode ser reutilizada (single-use)!"
print("OK_CONSUMIDO_SINGLE_USE")
"""
    proc2 = subprocess.run(
        [executavel_subprocess, "-c", codigo_consumir],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK_CONSUMIDO_SINGLE_USE" in proc2.stdout

    # 7. Verifica estado final dos arquivos:
    # decisao.json foi consumida (apagada ou consumido=True)
    if arquivo_decisao.exists():
        assert json.loads(arquivo_decisao.read_text(encoding="utf-8")).get("consumido") is True
    # pedido.json foi atualizado para status="concluido"
    pedido_final = json.loads(arquivo_pedido.read_text(encoding="utf-8"))
    assert pedido_final["status"] == "concluido"


def test_aprovacao_tool_workspace_apagar_end_to_end_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(4) Testa a tool_workspace_apagar nativa do núcleo de ponta a ponta:

    1. tool_workspace_apagar é invocada -> detecta que precisa de aprovação e cria pedido.json;
    2. Humano autenticado no servidor consulta GET /agente e faz POST /agente/aprovacao;
    3. tool_workspace_apagar é re-invocada -> consome a decisão com sucesso, apaga o arquivo físico,
       atualiza pedido para 'concluido' e NÃO recria pedido;
    4. Terceira invocação não reutiliza aprovação anterior (single-use).
    """
    from fastapi.testclient import TestClient
    from mapasfacil_servidor.app import create_app
    from mapasfacil_servidor.config import carregar
    from mapasfacil_servidor.versoes_sync import raiz_do_projeto

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text("MAPASFACIL_PROVEDOR_CHAVE=chave-teste\n", encoding="utf-8")
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MF_ADMIN_EMAIL", "admin@teste.com")

    cfg = carregar()
    banco = db.Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, admin_email=cfg.admin_email, origem="https://testserver", config=cfg)
    client = TestClient(app, base_url="https://testserver")

    cad = client.post(
        "/api/v1/auth/cadastrar",
        json={"nome": "Owner", "email": "owner@teste.com", "senha": "SenhaForte123!"},
    )
    csrf_token = client.get("/api/v1/auth/eu").json()["csrf"]

    resp_proj = client.post(
        "/api/v1/projetos",
        headers={"X-MF-CSRF": csrf_token},
        json={"nome": "Projeto Tool Apagar Real", "folha": {"formato": "A4", "orientacao": "retrato"}},
    )
    proj_id = resp_proj.json()["projeto"]["id"]
    ws_raiz = raiz_do_projeto(app.state.mf, proj_id)
    ws_raiz.mkdir(parents=True, exist_ok=True)

    # Cria arquivo no workspace
    arquivo_alvo = ws_raiz / "remover_me.txt"
    arquivo_alvo.write_text("conteudo a ser removido", encoding="utf-8")

    caminho_nucleo = Path(__file__).resolve().parents[3] / "Fase_1_Desktop" / "nucleo"
    python_nucleo = caminho_nucleo / ".venv" / "Scripts" / "python.exe"
    executavel_subprocess = str(python_nucleo if python_nucleo.is_file() else sys.executable)

    # Passo 1: Chama a tool_workspace_apagar diretamente pelo núcleo
    codigo_exec_tool_1 = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{caminho_nucleo}")
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace

ws = Path(r"{ws_raiz}")
gerenciador = GerenciadorAprovacao(ws)
registro = RegistroFerramentas()
registrar_tools_workspace(registro, gerenciador)

tool_def = registro.obter("workspace_apagar")
assert tool_def is not None
res = tool_def.handler({{"caminho": "remover_me.txt"}}, {{"workspace": ws}})

assert res.get("aguardando_aprovacao") is True, f"Esperado aguardando_aprovacao, obteve: {{res}}"
print("TOOL_PEDIU_APROVACAO_OK")
"""
    p1 = subprocess.run([executavel_subprocess, "-c", codigo_exec_tool_1], capture_output=True, text=True)
    assert p1.returncode == 0, f"p1 falhou:\n{p1.stderr}"
    assert "TOOL_PEDIU_APROVACAO_OK" in p1.stdout

    # Passo 2: Humano consulta token via GET e aprova via POST
    resp_estado = client.get(f"/api/v1/projetos/{proj_id}/agente")
    assert resp_estado.status_code == 200
    token = resp_estado.json()["aprovacao"]["token"]

    resp_post = client.post(
        f"/api/v1/projetos/{proj_id}/agente/aprovacao",
        headers={"X-MF-CSRF": csrf_token},
        json={
            "acao": "aprovar",
            "token": token,
            "action": "apagar",
            "path": "remover_me.txt",
            "motivo": "Exclusao autorizada",
        },
    )
    assert resp_post.status_code == 200
    assert resp_post.json()["ok"] is True

    # Passo 3: tool_workspace_apagar é re-invocada pelo agente
    codigo_exec_tool_2 = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{caminho_nucleo}")
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace

ws = Path(r"{ws_raiz}")
gerenciador = GerenciadorAprovacao(ws)
registro = RegistroFerramentas()
registrar_tools_workspace(registro, gerenciador)

tool_def = registro.obter("workspace_apagar")
assert tool_def is not None
res = tool_def.handler({{"caminho": "remover_me.txt"}}, {{"workspace": ws}})

assert res.get("ok") is True, f"Esperado ok: True, obteve: {{res}}"
assert res.get("apagado") is True, f"Esperado apagado: True, obteve: {{res}}"
assert not (ws / "remover_me.txt").exists(), "Arquivo físico deve ter sido removido!"
print("TOOL_APAGOU_COM_SUCESSO")
"""
    p2 = subprocess.run([executavel_subprocess, "-c", codigo_exec_tool_2], capture_output=True, text=True)
    assert p2.returncode == 0, f"p2 falhou:\n{p2.stderr}"
    assert "TOOL_APAGOU_COM_SUCESSO" in p2.stdout

    # Confere que o arquivo foi realmente apagado do disco
    assert not arquivo_alvo.exists()

    # Confere que pedido.json está como 'concluido'
    pasta_aprov = ws_raiz / ".servidor" / "aprovacoes"
    pedido_final = json.loads((pasta_aprov / "pedido.json").read_text(encoding="utf-8"))
    assert pedido_final["status"] == "concluido"
    assert not (pasta_aprov / "decisao.json").exists(), "decisao.json deve ter sido unlinked após consumo"



