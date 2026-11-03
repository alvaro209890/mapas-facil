"""W5-16 — o pool de produção leva a configuração do provedor e a chave do 9Router.

Antes disto o app subia com `pool=None`: todo chat respondia `SV-240` e nenhuma geração
acontecia. Este teste olha o **ambiente que o worker recebe** — sem abrir o núcleo de
verdade, usando o `fake_nucleo` como comando.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from mapasfacil_servidor.app import pool_de
from mapasfacil_servidor.config import carregar
from mapasfacil_servidor.db import Banco
from mapasfacil_servidor.ponte.worker import montar_env

RAIZ_SERVIDOR = Path(__file__).resolve().parents[1]
FAKE = [sys.executable, "-m", "mapasfacil_servidor.ponte.fake_nucleo", "--roteiro", "x.ndjson"]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text(
        "MAPASFACIL_PROVEDOR_CHAVE=chave-dedicada-do-mapas-facil\n"
        "MAPASFACIL_SEMA_AUTHKEY=sema-teste\n"
        "MAPASFACIL_PLANET_API_KEY=planet-teste\n",
        encoding="utf-8",
    )
    segredos.chmod(0o600)
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MAPASFACIL_MODELO_CHAT", "ag/gemini-3.8-flash-high")
    cfg = carregar()
    Banco(cfg.banco).migrar()
    return cfg


def test_pool_de_leva_provedor_e_segredos_para_o_worker(cfg):
    banco = Banco(cfg.banco)
    pool = pool_de(cfg, banco, cmd_base=FAKE)
    env = pool.env_por_projeto("projeto_x", Path("/tmp/projeto_x"))

    # 9Router / openai_compat (W5-16 / D33)
    assert env["MAPASFACIL_PROVEDOR"] == "openai_compat"
    assert env["MAPASFACIL_PROVEDOR_URL"].startswith("http")
    assert env["MAPASFACIL_MODELO_CHAT"] == "ag/gemini-3.8-flash-high"
    assert env["MAPASFACIL_RACIOCINIO"] == "high"
    # a chave vem do arquivo de segredos, não do ambiente do servidor
    assert env["MAPASFACIL_PROVEDOR_CHAVE"] == "chave-dedicada-do-mapas-facil"
    assert env["MAPASFACIL_SEMA_AUTHKEY"] == "sema-teste"
    # modo servidor e estado isolado por projeto
    assert env["MAPASFACIL_MODO"] == "servidor"
    assert env["MAPASFACIL_VAGAS_DIR"] == str(cfg.vagas)
    assert env["MAPASFACIL_MAX_JOBS"] == str(cfg.max_jobs)


def test_pool_de_usa_o_dono_do_projeto_como_sessao(cfg):
    banco = Banco(cfg.banco)
    con = banco.conectar()
    try:
        con.execute(
            "INSERT INTO usuarios (id, nome, email, senha_hash, papel, criado_em)"
            " VALUES ('u1', 'Ana', 'ana@imap.com.br', 'x', 'usuario', datetime('now'))"
        )
        con.execute(
            "INSERT INTO projetos (id, usuario_id, nome, estado, folha_formato, folha_orientacao,"
            " criado_em, atualizado_em)"
            " VALUES ('p1', 'u1', 'Boa Vista', 'aguardando_zip', 'A4', 'retrato',"
            " datetime('now'), datetime('now'))"
        )
        con.commit()
    finally:
        con.close()

    pool = pool_de(cfg, banco, cmd_base=FAKE)
    assert pool.env_por_projeto("p1", Path("/tmp/p1"))["MAPASFACIL_SESSAO_SERVIDOR"] == "u1"
    # projeto desconhecido não inventa usuário
    assert pool.env_por_projeto("nao_existe", Path("/tmp/x"))["MAPASFACIL_SESSAO_SERVIDOR"] == "sistema"


def test_cmd_base_aponta_para_o_python_do_nucleo(cfg):
    banco = Banco(cfg.banco)
    pool = pool_de(cfg, banco)
    assert pool.cmd_base[-3:] == ["-m", "mapasfacil_nucleo", "stdio"]
    assert pool.cmd_base[0] == str(cfg.python_nucleo)


def test_montar_env_nao_vaza_o_ambiente_do_servidor(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPASFACIL_PROVEDOR_CHAVE", "nao-deve-vazar")
    env = montar_env(projeto_raiz=tmp_path / "p", usuario_id="u1")
    assert "MAPASFACIL_PROVEDOR_CHAVE" not in env
