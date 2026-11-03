"""W5-18 — sugestões do chat vazio.

Critério do plano: cada sugestão é **texto de mensagem**, montada do que a importação já
sabe (folha, papéis das camadas, imóvel). Sem endpoint paralelo para executar nada.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.api import sugestoes as sug
from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.config import carregar
from mapasfacil_servidor.db import Banco

API = "/api/v1"
SENHA = "uma-senha-longa-123"


# ------------------------------------------------------------------- unidade


def test_sempre_traz_dinamica_do_ano_corrente_e_serie_completa():
    lista = sug.montar(folha={"formato": "A4", "orientacao": "paisagem"}, resumo=None, hoje=date(2026, 11, 3))
    textos = [s["texto"] for s in lista]
    assert textos[0] == "Faz a Dinâmica 2026"
    assert sug.SERIE_COMPLETA in textos


def test_uso_do_solo_so_com_avn_e_ac():
    sem = sug.montar(
        folha={"formato": "A4", "orientacao": "paisagem"},
        resumo={"workspace": {"shapefiles": [{"papel": "AVN"}]}},
    )
    assert "Mapa de uso do solo com quantitativos" not in [s["texto"] for s in sem]

    com = sug.montar(
        folha={"formato": "A4", "orientacao": "paisagem"},
        resumo={"workspace": {"shapefiles": [{"papel": "AVN"}, {"papel": "AC"}]}},
    )
    assert "Mapa de uso do solo com quantitativos" in [s["texto"] for s in com]


def test_qual_folha_so_com_imovel_alongado_em_retrato():
    bbox = {"xmin": 0.0, "ymin": 0.0, "xmax": 10000.0, "ymax": 1000.0}  # razão 10
    resumo = {"workspace": {"shapefiles": [{"papel": "ATP", "bbox": bbox}]}}

    retrato = sug.montar(folha={"formato": "A4", "orientacao": "retrato"}, resumo=resumo)
    assert "Qual folha deixa o mapa mais detalhado?" in [s["texto"] for s in retrato]

    paisagem = sug.montar(folha={"formato": "A4", "orientacao": "paisagem"}, resumo=resumo)
    assert "Qual folha deixa o mapa mais detalhado?" not in [s["texto"] for s in paisagem]


def test_imovel_quadrado_nao_sugere_folha():
    bbox = {"xmin": 0.0, "ymin": 0.0, "xmax": 1000.0, "ymax": 1100.0}  # razão 1,1
    resumo = {"workspace": {"shapefiles": [{"papel": "ATP", "bbox": bbox}]}}
    lista = sug.montar(folha={"formato": "A4", "orientacao": "retrato"}, resumo=resumo)
    assert "Qual folha deixa o mapa mais detalhado?" not in [s["texto"] for s in lista]


def test_sem_bbox_nao_sugere_folha():
    resumo = {"workspace": {"shapefiles": [{"papel": "ATP"}]}}
    lista = sug.montar(folha={"formato": "A4", "orientacao": "retrato"}, resumo=resumo)
    assert "Qual folha deixa o mapa mais detalhado?" not in [s["texto"] for s in lista]


def test_conferir_car_quando_o_recibo_foi_lido():
    resumo = {"imovel": {"car": "MT-1234-ABCD"}}
    lista = sug.montar(folha={"formato": "A4", "orientacao": "paisagem"}, resumo=resumo)
    assert "Confere as áreas do CAR neste mapa" in [s["texto"] for s in lista]


def test_papeis_vindos_da_contagem_tambem_contam():
    resumo = {"papeis": {"AVN": 2, "AC": 1}}
    lista = sug.montar(folha={"formato": "A4", "orientacao": "paisagem"}, resumo=resumo)
    assert "Mapa de uso do solo com quantitativos" in [s["texto"] for s in lista]


def test_toda_sugestao_tem_id_unico_e_porque():
    lista = sug.montar(
        folha={"formato": "A3", "orientacao": "retrato"},
        resumo={
            "workspace": {
                "shapefiles": [
                    {"papel": "ATP", "bbox": {"xmin": 0, "ymin": 0, "xmax": 9000, "ymax": 1000}},
                    {"papel": "AVN"},
                    {"papel": "AC"},
                ]
            },
            "imovel": {"car": "MT-1"},
        },
    )
    ids = [s["id"] for s in lista]
    assert len(ids) == len(set(ids))
    assert all(s["porque"] and s["texto"] for s in lista)


# ------------------------------------------------------------------- rota


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text(
        "MAPASFACIL_PROVEDOR_CHAVE=c\nMAPASFACIL_SEMA_AUTHKEY=s\nMAPASFACIL_PLANET_API_KEY=p\n",
        encoding="utf-8",
    )
    segredos.chmod(0o600)
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    cfg = carregar()
    banco = Banco(cfg.banco)
    banco.migrar()
    app = create_app(banco=banco, origem="https://testserver", config=cfg)
    with TestClient(app, base_url="https://testserver") as c:
        yield c, banco


def _entrar(cliente) -> tuple[str, dict]:
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Ana", "email": "ana@imap.com.br", "senha": SENHA},
    )
    csrf = cliente.get(f"{API}/auth/eu").json()["csrf"]
    projeto = cliente.post(
        f"{API}/projetos",
        json={"nome": "Boa Vista", "folha": {"formato": "A3", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": csrf},
    ).json()["projeto"]
    return csrf, projeto


def test_rota_devolve_sugestoes_do_projeto(cliente):
    c, _banco = cliente
    _csrf, projeto = _entrar(c)
    resposta = c.get(f"{API}/projetos/{projeto['id']}/sugestoes")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["projeto_id"] == projeto["id"]
    textos = [s["texto"] for s in dados["sugestoes"]]
    assert any("Dinâmica" in t for t in textos)
    assert sug.SERIE_COMPLETA in textos


def test_rota_usa_o_resumo_da_importacao(cliente):
    c, banco = cliente
    _csrf, projeto = _entrar(c)
    con = banco.conectar()
    try:
        con.execute(
            "INSERT INTO importacoes (id, projeto_id, upload_id, estado, fase, resumo, criada_em)"
            " VALUES (?, ?, ?, 'pronto', 'pronto', ?, datetime('now'))",
            (
                "imp_1",
                projeto["id"],
                "up_1",
                '{"workspace": {"shapefiles": [{"papel": "AVN"}, {"papel": "AC"}]}}',
            ),
        )
        con.commit()
    finally:
        con.close()
    textos = [
        s["texto"]
        for s in c.get(f"{API}/projetos/{projeto['id']}/sugestoes").json()["sugestoes"]
    ]
    assert "Mapa de uso do solo com quantitativos" in textos


def test_rota_em_projeto_alheio_404(cliente):
    c, _banco = cliente
    _csrf, projeto = _entrar(c)
    c.post(f"{API}/auth/sair")
    c.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Bia", "email": "bia@imap.com.br", "senha": SENHA},
    )
    assert c.get(f"{API}/projetos/{projeto['id']}/sugestoes").status_code == 404
