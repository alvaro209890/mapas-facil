# Conta local e-mail+senha (F1-14 / M5).

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo import sessao
from mapasfacil_nucleo.__main__ import processar_linha
from mapasfacil_nucleo.contas import servico as contas_servico
from mapasfacil_nucleo.contas.banco import caminho_banco
from mapasfacil_nucleo.protocolo import envelope_req


@pytest.fixture
def pasta_contas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pasta = tmp_path / "contas"
    pasta.mkdir()
    monkeypatch.setenv("MAPASFACIL_CONTAS_DIR", str(pasta))
    contas_servico.configurar_diretorio(pasta)
    sessao.resetar()
    yield pasta
    sessao.resetar()
    contas_servico.configurar_diretorio(None)


def _ndjson(metodo: str, params: dict | None = None) -> dict:
    return json.loads(processar_linha(json.dumps(envelope_req(metodo, params or {}))))


def test_criar_entrar_e_lembrar(pasta_contas: Path):
    r = _ndjson(
        "conta.criar",
        {"email": " Tecnico@Escritorio.COM ", "senha": "segredo99", "nome": "Ana"},
    )
    assert r["ok"] is True
    conta = r["resultado"]["conta"]
    assert conta["email"] == "tecnico@escritorio.com"
    assert conta["nome"] == "Ana"
    assert "senha" not in conta and "senha_hash" not in conta
    assert r["resultado"]["sessao"]["estado"] == "conectado"
    assert sessao.conectada()

    # Senha não fica em claro no arquivo.
    bruto = caminho_banco(pasta_contas).read_bytes()
    assert b"segredo99" not in bruto

    _ndjson("conta.sair", {})
    assert not sessao.conectada()

    r2 = _ndjson(
        "conta.entrar",
        {"email": "tecnico@escritorio.com", "senha": "segredo99", "lembrar_neste_pc": True},
    )
    assert r2["ok"] is True
    assert r2["resultado"]["conta"]["id"] == conta["id"]

    sessao.resetar()
    restaurado = contas_servico.restaurar_se_lembrada()
    assert restaurado["estado"] == "conectado"
    assert restaurado["conta"]["email"] == "tecnico@escritorio.com"


def test_senha_errada_e_email_duplicado(pasta_contas: Path):
    assert _ndjson("conta.criar", {"email": "a@b.com.br", "senha": "abcdefgh"})["ok"]
    dup = _ndjson("conta.criar", {"email": "A@B.com.br", "senha": "abcdefgh"})
    assert dup["ok"] is False
    assert dup["erro"]["codigo"] == "AUTH-070"

    _ndjson("conta.sair", {})
    ruim = _ndjson("conta.entrar", {"email": "a@b.com.br", "senha": "errada!!!!"})
    assert ruim["ok"] is False
    assert ruim["erro"]["codigo"] == "AUTH-002"
    # Mensagem genérica — não vaza se o e-mail existe.
    assert "incorretos" in ruim["erro"]["mensagem"].lower()


def test_senha_fraca(pasta_contas: Path):
    r = _ndjson("conta.criar", {"email": "x@y.com", "senha": "curta"})
    assert r["ok"] is False
    assert r["erro"]["codigo"] == "AUTH-003"


def test_esquecer_este_pc(pasta_contas: Path):
    _ndjson("conta.criar", {"email": "z@y.com", "senha": "abcdefgh"})
    r = _ndjson("conta.sair", {"esquecer_este_pc": True})
    assert r["ok"] is True
    assert r["resultado"]["esquecido"] is True
    assert not sessao.conectada()
    assert contas_servico.repositorio().buscar_por_email("z@y.com") is None
