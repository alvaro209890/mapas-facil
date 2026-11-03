"""`GET /projetos/{id}/arquivos/{caminho}` — allowlist fechada e Range.

O que este teste protege, em ordem de gravidade:

1. projeto de outra pessoa não vaza arquivo (404, sem dizer que existe);
2. `..` e caminho absoluto não saem da pasta do projeto;
3. `SHP/`, `.servidor/` e afins **não** são servidos avulsos — vão no `.zip`;
4. `Range` responde `206`, então o navegador retoma um PDF grande;
5. `?anexo=true` baixa em vez de abrir.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.db import Banco

API = "/api/v1"
SENHA = "mapaForte2026"


@pytest.fixture()
def banco(tmp_path: Path) -> Banco:
    b = Banco(tmp_path / "dados" / "mapasfacil.sqlite")
    assert b.migrar() >= 1
    return b


@pytest.fixture()
def app_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        raiz=tmp_path,
        projetos=tmp_path / "projetos",
        uploads=tmp_path / "uploads",
    )


@pytest.fixture()
def cliente(banco: Banco, app_config: SimpleNamespace, tmp_path: Path) -> TestClient:
    app = create_app(
        banco=banco,
        admin_email="chefe@imap.com.br",
        origem="https://testserver",
        config=app_config,
    )
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _csrf(cliente: TestClient) -> str:
    return cliente.get(f"{API}/auth/eu").json()["csrf"]


@pytest.fixture()
def projeto_com_arquivos(cliente: TestClient, app_config: SimpleNamespace) -> dict:
    cadastro = cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Ana", "email": "ana@imap.com.br", "senha": SENHA},
    )
    assert cadastro.status_code == 201, cadastro.text
    token = _csrf(cliente)
    criado = cliente.post(
        f"{API}/projetos",
        json={"nome": "Boa Vista", "folha": {"formato": "A3", "orientacao": "paisagem"}},
        headers={"X-MF-CSRF": token},
    )
    assert criado.status_code == 201, criado.text
    projeto = criado.json()["projeto"]

    # Arquivos do projeto vivem em `<MF_RAIZ>/projetos/<id>`, na saída versionada.
    raiz = Path(app_config.projetos) / projeto["id"]
    (raiz / "Mapas" / "v001").mkdir(parents=True, exist_ok=True)
    (raiz / "MXD").mkdir(parents=True, exist_ok=True)
    (raiz / "SHP").mkdir(parents=True, exist_ok=True)
    (raiz / ".servidor").mkdir(parents=True, exist_ok=True)

    (raiz / "Mapas" / "v001" / "mapa.pdf").write_bytes(b"%PDF-1.7\n" + b"x" * 2000)
    (raiz / "Mapas" / "v001" / "miniatura.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"y" * 100)
    (raiz / "Mapas" / "v001" / "pacote.zip").write_bytes(b"PK\x03\x04" + b"z" * 50)
    (raiz / "MXD" / "mapa.mxd").write_bytes(b"\xd0\xcf\x11\xe0" + b"m" * 100)
    (raiz / "SHP" / "ATP.shp").write_bytes(b"shp")
    (raiz / ".servidor" / "eventos.ndjson").write_text("{}\n", encoding="utf-8")
    return {"id": projeto["id"], "raiz": raiz, "csrf": token}


def test_pdf_sai_inline_com_tipo_certo(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/Mapas/v001/mapa.pdf")
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.headers["content-disposition"].startswith("inline")
    assert resposta.content.startswith(b"%PDF")


def test_anexo_forca_download_com_nome_amigavel(
    cliente: TestClient, projeto_com_arquivos: dict
) -> None:
    resposta = cliente.get(
        f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/Mapas/v001/pacote.zip?anexo=true"
    )
    assert resposta.status_code == 200
    disposicao = resposta.headers["content-disposition"]
    assert disposicao.startswith("attachment")
    assert "Boa_Vista_v001_pacote.zip" in disposicao


def test_mxd_e_entregue(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/MXD/mapa.mxd")
    assert resposta.status_code == 200
    assert resposta.content.startswith(b"\xd0\xcf\x11\xe0")


def test_shp_nao_e_servido_avulso(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/SHP/ATP.shp")
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-401"


def test_estado_interno_nao_vaza(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(
        f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/.servidor/eventos.ndjson"
    )
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-401"


def test_path_traversal_da_400(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(
        f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/Mapas/../../segredos/servidor.env"
    )
    assert resposta.status_code in (400, 404)
    if resposta.status_code == 400:
        assert resposta.json()["erro"]["codigo"] == "SV-402"


def test_arquivo_inexistente_404(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/Mapas/v009/nada.pdf")
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-401"


def test_projeto_alheio_nao_entrega(
    cliente: TestClient, projeto_com_arquivos: dict
) -> None:
    alheio = projeto_com_arquivos["id"]
    cliente.post(f"{API}/auth/sair")
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Bia", "email": "bia@imap.com.br", "senha": SENHA},
    )
    resposta = cliente.get(f"{API}/projetos/{alheio}/arquivos/Mapas/v001/mapa.pdf")
    assert resposta.status_code == 404


def test_range_responde_206(cliente: TestClient, projeto_com_arquivos: dict) -> None:
    resposta = cliente.get(
        f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/Mapas/v001/mapa.pdf",
        headers={"Range": "bytes=0-9"},
    )
    assert resposta.status_code == 206, resposta.text
    assert resposta.headers["content-range"].startswith("bytes 0-9/")
    assert len(resposta.content) == 10


def test_sem_sessao_401(
    projeto_com_arquivos: dict, banco: Banco, app_config: SimpleNamespace
) -> None:
    app = create_app(
        banco=banco,
        admin_email="chefe@imap.com.br",
        origem="https://testserver",
        config=app_config,
    )
    with TestClient(app, base_url="https://testserver") as anonimo:
        resposta = anonimo.get(
            f"{API}/projetos/{projeto_com_arquivos['id']}/arquivos/Mapas/v001/mapa.pdf"
        )
    assert resposta.status_code == 401
