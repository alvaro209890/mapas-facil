"""W6-10 — a SPA servida pelo FastAPI.

As três garantias estão testadas aqui: `index.html` sem cache, asset com hash imutável e rota
do SPA devolvendo o HTML (recarregar `/projetos/p1` no meio do trabalho não pode dar 404).
Mais uma que evita acidente feio: `/api/...` desconhecido responde **erro de API**, não a SPA.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.db import Banco


@pytest.fixture()
def dist(tmp_path: Path) -> Path:
    pasta = tmp_path / "web" / "dist"
    (pasta / "assets").mkdir(parents=True)
    (pasta / "index.html").write_text(
        "<!doctype html><html><body><div id='raiz'>app</div></body></html>", encoding="utf-8"
    )
    (pasta / "assets" / "index-7f3a.js").write_text("console.log('app')", encoding="utf-8")
    (pasta / "assets" / "index-7f3a.css").write_text("body{margin:0}", encoding="utf-8")
    (pasta / "logo.svg").write_text("<svg/>", encoding="utf-8")
    return pasta


@pytest.fixture()
def cliente(tmp_path: Path, dist: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MF_WEB_DIST", str(dist))
    banco = Banco(tmp_path / "dados" / "mapasfacil.sqlite")
    assert banco.migrar() >= 1
    config = SimpleNamespace(raiz=tmp_path, projetos=tmp_path / "projetos", uploads=tmp_path / "uploads")
    app = create_app(banco=banco, admin_email="chefe@imap.com.br", origem="https://testserver", config=config)
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def test_index_sem_cache(cliente: TestClient) -> None:
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    assert resposta.headers["cache-control"] == "no-cache, must-revalidate"
    assert "raiz" in resposta.text


def test_asset_com_hash_e_imutavel(cliente: TestClient) -> None:
    resposta = cliente.get("/assets/index-7f3a.js")
    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resposta.headers["content-type"].startswith("text/javascript")


def test_css_tambem(cliente: TestClient) -> None:
    resposta = cliente.get("/assets/index-7f3a.css")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/css")


def test_rota_do_spa_devolve_html(cliente: TestClient) -> None:
    for rota in ("/projetos", "/projetos/p1", "/projetos/p1/versoes/2", "/admin"):
        resposta = cliente.get(rota)
        assert resposta.status_code == 200, rota
        assert "raiz" in resposta.text, rota
        assert resposta.headers["cache-control"] == "no-cache, must-revalidate"


def test_arquivo_estatico_na_raiz_do_dist(cliente: TestClient) -> None:
    resposta = cliente.get("/logo.svg")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "image/svg+xml"


def test_api_desconhecida_nao_cai_na_spa(cliente: TestClient) -> None:
    resposta = cliente.get("/api/v1/nao-existe")
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-404"


def test_asset_inexistente_404_sem_spa(cliente: TestClient) -> None:
    resposta = cliente.get("/assets/some-que-nao-existe.js")
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-401"


def test_sem_build_o_app_sobe_e_diz_que_nao_tem_spa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MF_WEB_DIST", str(tmp_path / "nao-existe"))
    banco = Banco(tmp_path / "dados2" / "mapasfacil.sqlite")
    assert banco.migrar() >= 1
    app = create_app(banco=banco, admin_email="chefe@imap.com.br", origem="https://testserver")
    with TestClient(app, base_url="https://testserver") as c:
        saude = c.get("/api/v1/saude")
        assert saude.status_code == 200
        assert saude.json()["spa"] is False
        assert c.get("/").status_code == 404


def test_sem_build_nao_quebra_a_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MF_WEB_DIST", str(tmp_path / "nao-existe"))
    banco = Banco(tmp_path / "dados3" / "mapasfacil.sqlite")
    assert banco.migrar() >= 1
    app = create_app(banco=banco, admin_email="chefe@imap.com.br", origem="https://testserver")
    with TestClient(app, base_url="https://testserver") as c:
        assert c.post(
            "/api/v1/auth/cadastrar",
            json={"nome": "Ana", "email": "ana@imap.com.br", "senha": "mapaForte2026"},
        ).status_code == 201
