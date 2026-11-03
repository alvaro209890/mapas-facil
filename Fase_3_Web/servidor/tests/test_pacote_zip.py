"""Testes do endpoint de download do pacote de entrega completo (W10-10).

Valida:
- GET /api/v1/projetos/{id}/versoes/{versao}/pacote.zip:
  * 200 OK com application/zip e nome do arquivo correto;
  * Arquivo .zip gerado contém LEIA-ME.txt e arquivos de entrega;
  * 404 SV-240 se a versão não existir.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.db import Banco

API = "/api/v1"
SENHA = "uma-senha-longa-123"


@pytest.fixture
def banco(tmp_path: Path) -> Banco:
    b = Banco(tmp_path / "dados" / "mapasfacil.sqlite")
    assert b.migrar() >= 1
    return b


@pytest.fixture
def cliente(banco: Banco) -> TestClient:
    app = create_app(banco=banco, admin_email="admin@imap.com.br", origem="https://testserver")
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def csrf(cliente: TestClient) -> str:
    r = cliente.get(f"{API}/auth/eu")
    assert r.status_code == 200, r.text
    return r.json()["csrf"]


def test_download_pacote_zip_sucesso_e_conteudo(cliente: TestClient, banco: Banco, tmp_path: Path) -> None:
    # 1. Cadastra e autentica
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Carla", "email": "carla@imap.com.br", "senha": SENHA},
    )
    token_csrf = csrf(cliente)

    # 2. Cria projeto
    r_proj = cliente.post(
        f"{API}/projetos",
        json={"nome": "Fazenda Boa Esperança", "folha": {"formato": "A4", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": token_csrf},
    )
    assert r_proj.status_code == 201
    proj_id = r_proj.json()["projeto"]["id"]

    # 3. Cria pasta física para a versão 1
    pasta_versao = tmp_path / "projetos" / proj_id / "versoes" / "001"
    pasta_versao.mkdir(parents=True)
    pasta_shp = pasta_versao / "SHP"
    pasta_shp.mkdir()
    (pasta_shp / "PERIMETRO.shp").write_bytes(b"PERIMETRO_BINARIO")
    (pasta_versao / "mapa.pdf").write_bytes(b"%PDF-1.4 DADOS DO MAPA")

    # Registra a versão 1 no banco
    with banco.conectar() as con:
        con.execute(
            "INSERT INTO versoes (projeto_id, numero, pasta, conforme, miniatura, artefatos, validacao, criada_em) "
            "VALUES (?, 1, ?, 1, NULL, '{}', '{}', datetime('now'))",
            (proj_id, str(pasta_versao)),
        )
        con.commit()

    # 4. Requisita download do pacote
    resp = cliente.get(f"{API}/projetos/{proj_id}/versoes/1/pacote.zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers["content-disposition"]
    assert "_v001.zip" in resp.headers["content-disposition"]

    # 5. Valida estrutura interna do zip recebido
    with zipfile.ZipFile(io.BytesIO(resp.content), "r") as zf:
        nomes = zf.namelist()
        assert "LEIA-ME.txt" in nomes
        assert "SHP/PERIMETRO.shp" in nomes
        assert "Mapas/mapa.pdf" in nomes

        leia_me = zf.read("LEIA-ME.txt").decode("utf-8")
        assert "Fazenda Boa Esperança" in leia_me


def test_download_pacote_zip_versao_inexistente_retorna_404(cliente: TestClient) -> None:
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Carla", "email": "carla2@imap.com.br", "senha": SENHA},
    )
    token_csrf = csrf(cliente)
    r_proj = cliente.post(
        f"{API}/projetos",
        json={"nome": "Fazenda Modelo", "folha": {"formato": "A4", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": token_csrf},
    )
    proj_id = r_proj.json()["projeto"]["id"]

    resp = cliente.get(f"{API}/projetos/{proj_id}/versoes/99/pacote.zip")
    assert resp.status_code == 404
    dados = resp.json()
    assert dados["erro"]["codigo"] == "SV-240"
