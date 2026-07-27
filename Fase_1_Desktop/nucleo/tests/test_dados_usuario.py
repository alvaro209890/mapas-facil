"""Dados por usuário em Documentos/database/MapasFacil + DeepSeek no login."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo import cofre, sessao
from mapasfacil_nucleo.__main__ import processar_linha
from mapasfacil_nucleo.agente.provisao import (
    ler_chave_projeto,
    sincronizar_chave_projeto_no_cofre,
)
from mapasfacil_nucleo.camadas import resolver as resolver_camadas
from mapasfacil_nucleo.contas import servico as contas_servico
from mapasfacil_nucleo.dados import (
    arquivar_artefatos_do_job,
    garantir_arvore_usuario,
    slug_usuario,
)
from mapasfacil_nucleo.protocolo import envelope_req


@pytest.fixture
def raiz_dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPASFACIL_DATABASE_ROOT", str(tmp_path))
    monkeypatch.setenv("MAPASFACIL_DADOS", str(tmp_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MAPASFACIL_PROVISAO_PATH", raising=False)
    pasta_contas = tmp_path / "contas"
    pasta_contas.mkdir()
    contas_servico.configurar_diretorio(pasta_contas)
    mem = cofre.BackendMemoria()
    cofre.configurar_backend(mem)
    sessao.resetar()
    yield tmp_path
    sessao.resetar()
    contas_servico.configurar_diretorio(None)
    cofre.configurar_backend(None)


def _ndjson(metodo: str, params: dict | None = None) -> dict:
    return json.loads(processar_linha(json.dumps(envelope_req(metodo, params or {}))))


def test_slug_usuario():
    assert slug_usuario("Ana@Firma.COM.br") == "ana_at_firma_com_br"


def test_login_cria_pasta_e_ativa_deepseek(raiz_dados: Path, monkeypatch: pytest.MonkeyPatch):
    # provisão local (sem tocar secrets.local.json real)
    provisao = raiz_dados / "provisao.local.json"
    provisao.write_text(
        json.dumps({"deepseek_api_key": "sk-projeto-teste-1234567890"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MAPASFACIL_PROVISAO_PATH", str(provisao))
    # Isola secrets do monorepo (assinatura recebe a chave a ler)
    monkeypatch.setattr(
        "mapasfacil_nucleo.agente.provisao._ler_secrets_repo",
        lambda _chave="deepseek_api_key": None,
    )

    r = _ndjson(
        "conta.criar",
        {"email": "tecnico@mapa.local", "senha": "segredo99", "nome": "Tec"},
    )
    assert r["ok"] is True
    dados = r["resultado"]["dados"]
    assert dados["deepseek_projeto"] is True
    pasta = Path(dados["pasta_usuario"])
    assert pasta.is_dir()
    assert (pasta / "chats").is_dir()
    assert (pasta / "mxd").is_dir()
    assert (pasta / "pdf").is_dir()
    assert (pasta / "workspace").is_dir()
    assert cofre.existe("deepseek_api_key")
    assert ler_chave_projeto() == "sk-projeto-teste-1234567890"
    assert sincronizar_chave_projeto_no_cofre()["ok"] is True

    ativo = contas_servico.usuario_ativo()
    assert ativo is not None
    assert ativo["email"] == "tecnico@mapa.local"
    assert Path(ativo["chats"]).is_dir()


def test_login_provisiona_sema_e_planet(raiz_dados: Path, monkeypatch: pytest.MonkeyPatch):
    """30 das 41 camadas exigem `sema_authkey`: ela tem de chegar ao cofre
    sozinha no login, senão o usuário final bate em `NU-102`."""
    provisao = raiz_dados / "provisao.local.json"
    provisao.write_text(
        json.dumps(
            {
                "deepseek_api_key": "sk-projeto-teste-1234567890",
                "sema_authkey": "authkey-sema-de-teste",
                "planet_api_key": "PLAK-de-teste",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MAPASFACIL_PROVISAO_PATH", str(provisao))
    monkeypatch.setattr(
        "mapasfacil_nucleo.agente.provisao._ler_secrets_repo",
        lambda _chave="deepseek_api_key": None,
    )

    r = _ndjson("conta.criar", {"email": "campo@mapa.local", "senha": "segredo99"})
    assert r["ok"] is True

    assert cofre.existe("sema_authkey")
    assert cofre.existe("planet_api_key")

    # A camada resolve a chave do cofre em vez de exigir configuração manual.
    camada = {"id": "car_sema", "auth": "sema_authkey"}
    assert resolver_camadas._obter_authkey(camada) == "authkey-sema-de-teste"


def test_arquivar_artefatos(raiz_dados: Path):
    pasta = garantir_arvore_usuario(email="a@b.com", raiz=raiz_dados)
    ws = pasta / "workspace"
    (ws / "Mapas").mkdir(parents=True)
    pdf = ws / "Mapas" / "saida.pdf"
    mxd = ws / "Mapas" / "saida.mxd"
    pdf.write_bytes(b"%PDF")
    mxd.write_bytes(b"MXD")
    copiados = arquivar_artefatos_do_job(
        {"pdf": "Mapas/saida.pdf", "mxd": {"caminho": "Mapas/saida.mxd"}},
        raiz_workspace=ws,
        pasta_usuario_destino=pasta,
    )
    assert "pdf/saida.pdf" in copiados
    assert "mxd/saida.mxd" in copiados
    assert (pasta / "pdf" / "saida.pdf").is_file()
    assert (pasta / "mxd" / "saida.mxd").is_file()
