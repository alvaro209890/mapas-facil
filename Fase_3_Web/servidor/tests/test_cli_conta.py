"""W3-23/W3-24 — CLI `conta` ponta a ponta e redação de log."""

from __future__ import annotations

import logging

from mapasfacil_servidor import logs_redigidos, __main__ as cli
from mapasfacil_servidor.auth import contas
from mapasfacil_servidor.db import Banco


def _ambiente(monkeypatch, tmp_path):
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
    return raiz


def test_cli_cria_lista_e_bloqueia(monkeypatch, tmp_path, capsys):
    raiz = _ambiente(monkeypatch, tmp_path)

    assert cli.main(["migrar"]) == 0
    assert "schema na versão" in capsys.readouterr().out

    codigo = cli.main(
        ["conta", "criar", "--email", "ana@b.com", "--nome", "Ana"]
    )
    saida = capsys.readouterr().out
    assert codigo == 0, saida
    assert "senha temporária" in saida

    assert cli.main(["conta", "listar"]) == 0
    listado = capsys.readouterr().out
    assert "ana@b.com" in listado and "ativo" in listado

    assert cli.main(["conta", "bloquear", "--email", "ana@b.com"]) == 0
    assert "bloqueado" in capsys.readouterr().out

    assert cli.main(["conta", "desbloquear", "--email", "ana@b.com"]) == 0
    assert "ativo" in capsys.readouterr().out

    banco = Banco(raiz / "dados" / "mapasfacil.sqlite")
    con = banco.conectar()
    try:
        usuario = contas.buscar_por_email(con, "ana@b.com")
        assert usuario is not None and usuario.ativo is True
        assert usuario.trocar_senha is True
    finally:
        con.close()


def test_cli_conta_criar_sem_email_devolve_erro(monkeypatch, tmp_path, capsys):
    _ambiente(monkeypatch, tmp_path)
    assert cli.main(["conta", "criar", "--nome", "Sem Email"]) == 2
    assert "SV-016" in capsys.readouterr().err


def test_cli_bloquear_email_inexistente(monkeypatch, tmp_path, capsys):
    _ambiente(monkeypatch, tmp_path)
    assert cli.main(["conta", "bloquear", "--email", "ninguem@b.com"]) == 2
    assert "SV-034" in capsys.readouterr().err


def test_cli_promove_admin_por_env(monkeypatch, tmp_path, capsys):
    raiz = _ambiente(monkeypatch, tmp_path)
    assert cli.main(["conta", "criar", "--email", "chefe@imap.com.br", "--nome", "Chefe"]) == 0
    capsys.readouterr()
    con = Banco(raiz / "dados" / "mapasfacil.sqlite").conectar()
    try:
        assert contas.buscar_por_email(con, "chefe@imap.com.br").papel == "admin"
    finally:
        con.close()


# --- redação --------------------------------------------------------------


def test_redigir_mascara_cpf_chave_e_email():
    texto = "cpf 123.456.789-09 chave sk-abcdef123456 ana.silva@imap.com.br authkey=ABC"
    saida = logs_redigidos.redigir(texto, email=True)
    assert "123.456.789-09" not in saida
    assert "abcdef123456" not in saida
    assert "ana.silva@" not in saida
    assert "ABC" != saida.split("authkey=")[1]


def test_filtro_de_logging_redige_na_gravacao(caplog):
    logger = logging.getLogger("teste.redacao")
    logger.addFilter(logs_redigidos.FiltroRedacao())
    with caplog.at_level(logging.INFO):
        logger.info("falhou para 123.456.789-09 com sk-ZZZZ12345678")
    assert "123.456.789-09" not in caplog.text
    assert "ZZZZ12345678" not in caplog.text
