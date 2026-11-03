"""`GET /projetos/{id}/palco/{job_id}/{sub}/{arquivo}` — allowlist do palco (W7-05).

O que este teste protege, em ordem de gravidade:

1. projeto de outra pessoa não vaza asset de palco (404, sem dizer que existe);
2. `..`, caminho absoluto e subpasta fora da lista não saem da pasta do job;
3. extensão fora da allowlist (`.geojson`, `.png`) não é servida;
4. o GeoJSON sai com tipo `application/geo+json` e cache privado;
5. o PNG do raster sai com `image/png`.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.db import Banco

API = "/api/v1"
SENHA = "mapaForte2026"
JOB = "01JOBPALCO0000000000000000"


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
def cliente(banco: Banco, app_config: SimpleNamespace) -> TestClient:
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


def _projeto(cliente: TestClient, email: str) -> dict:
    cadastro = cliente.post(
        f"{API}/auth/cadastrar", json={"nome": "Ana", "email": email, "senha": SENHA}
    )
    assert cadastro.status_code == 201, cadastro.text
    token = _csrf(cliente)
    criado = cliente.post(
        f"{API}/projetos",
        json={"nome": "Boa Vista", "folha": {"formato": "A4", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": token},
    )
    assert criado.status_code == 201, criado.text
    return {"id": criado.json()["projeto"]["id"], "csrf": token}


@pytest.fixture()
def projeto_com_palco(cliente: TestClient, app_config: SimpleNamespace) -> dict:
    projeto = _projeto(cliente, "ana@imap.com.br")
    raiz = Path(app_config.projetos) / projeto["id"]
    preview = raiz / "Mapas" / ".preview" / JOB
    (preview / "camadas").mkdir(parents=True, exist_ok=True)
    (preview / "layout").mkdir(parents=True, exist_ok=True)
    (preview / "raster").mkdir(parents=True, exist_ok=True)
    (preview / "camadas" / "avn.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8"
    )
    (preview / "layout" / "titulo_caixa.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"t" * 40)
    (preview / "raster" / "basemap.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"r" * 40)
    (preview / "camadas" / "segredo.txt").write_text("nao deve sair", encoding="utf-8")
    (raiz / "SHP").mkdir(parents=True, exist_ok=True)
    (raiz / "SHP" / "ATP.shp").write_bytes(b"shp")
    return {"id": projeto["id"], "raiz": raiz, "csrf": projeto["csrf"]}


def test_geojson_do_palco_sai_com_tipo_e_cache_privado(
    cliente: TestClient, projeto_com_palco: dict
) -> None:
    url = f"{API}/projetos/{projeto_com_palco['id']}/palco/{JOB}/camadas/avn.geojson"
    resposta = cliente.get(url)
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"].startswith("application/geo+json")
    assert resposta.headers["cache-control"] == "private, max-age=3600"
    assert resposta.json()["type"] == "FeatureCollection"


def test_png_do_layout_e_do_raster_saem(cliente: TestClient, projeto_com_palco: dict) -> None:
    for resto in ("layout/titulo_caixa.png", "raster/basemap.png"):
        resposta = cliente.get(
            f"{API}/projetos/{projeto_com_palco['id']}/palco/{JOB}/{resto}"
        )
        assert resposta.status_code == 200, resto
        assert resposta.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    "resto",
    [
        "camadas/%2e%2e/camadas/avn.geojson",
        "../../SHP/ATP.shp",
        "camadas/segredo.txt",
        "SHP/ATP.shp",
        "outra_pasta/avn.geojson",
        "camadas",
        "camadas/avn.geojson/extra",
    ],
)
def test_allowlist_recusa_o_que_nao_e_asset_de_palco(
    cliente: TestClient, projeto_com_palco: dict, resto: str
) -> None:
    resposta = cliente.get(
        f"{API}/projetos/{projeto_com_palco['id']}/palco/{JOB}/{resto}"
    )
    assert resposta.status_code == 404, f"{resto} -> {resposta.status_code}"


def test_resolver_recusa_ponto_ponto_cru(tmp_path: Path) -> None:
    """O cliente HTTP normaliza `..`; a rota não pode confiar nisso."""
    from mapasfacil_servidor.api.palco import _resolver
    from mapasfacil_servidor.erros import ErroServidor

    base = tmp_path / "Mapas" / ".preview" / JOB / "camadas"
    base.mkdir(parents=True)
    (base / "avn.geojson").write_text("{}", encoding="utf-8")
    for resto in ("camadas/../camadas/avn.geojson", "/etc/passwd", "camadas/../../x.geojson"):
        with pytest.raises(ErroServidor):
            _resolver(tmp_path, JOB, resto)


def test_job_inexistente_da_404(cliente: TestClient, projeto_com_palco: dict) -> None:
    resposta = cliente.get(
        f"{API}/projetos/{projeto_com_palco['id']}/palco/01JOBNAOEXISTE/camadas/avn.geojson"
    )
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-402"


def test_projeto_de_outro_usuario_nao_vaza_palco(
    cliente: TestClient, projeto_com_palco: dict
) -> None:
    url = f"{API}/projetos/{projeto_com_palco['id']}/palco/{JOB}/camadas/avn.geojson"
    cliente.post(f"{API}/auth/sair")
    _projeto(cliente, "bruno@imap.com.br")
    resposta = cliente.get(url)
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "SV-031"
