"""W2-05 — registro de versão: lê o que o núcleo escreveu, sem inventar conformidade."""

from __future__ import annotations

import json
from pathlib import Path

from mapasfacil_servidor.ponte import versao


def _projeto(tmp_path: Path) -> Path:
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    return raiz


def test_sem_pasta_de_versao(tmp_path):
    raiz = _projeto(tmp_path)
    assert versao.ultima_versao(raiz) == 0
    registro = versao.montar(raiz, 1)
    assert registro.pasta == "Mapas/v001"
    assert registro.artefatos == {}
    assert registro.conforme is False


def test_copia_artefatos_e_validacao(tmp_path):
    raiz = _projeto(tmp_path)
    pasta = raiz / "Mapas" / "v002"
    pasta.mkdir(parents=True)
    (pasta / "mapa.mxd").write_bytes(b"mxd")
    (pasta / "mapa.pdf").write_bytes(b"%PDF")
    (pasta / "preview.png").write_bytes(b"\x89PNG")
    (pasta / "planilha.xlsx").write_bytes(b"PK")
    (pasta / "serie").mkdir()
    (pasta / "serie" / "2025.pdf").write_bytes(b"%PDF")
    (pasta / "validacao.json").write_text(
        json.dumps(
            {
                "checks": [
                    {"nome": "H05", "severidade": "HARD", "ok": True},
                    {"nome": "S12", "severidade": "SOFT", "ok": False},
                ]
            }
        ),
        encoding="utf-8",
    )

    registro = versao.montar(raiz, 2)
    assert registro.numero == 2
    assert registro.pasta == "Mapas/v002"
    assert registro.conforme is True, "SOFT reprovado não tira conformidade"
    assert registro.miniatura == "Mapas/v002/preview.png"
    assert set(registro.artefatos) == {"mxd", "pdf", "png", "xlsx"}
    assert versao.ultima_versao(raiz) == 2


def test_hard_reprovado_marca_nao_conforme(tmp_path):
    raiz = _projeto(tmp_path)
    pasta = raiz / "Mapas" / "v001"
    pasta.mkdir(parents=True)
    (pasta / "validacao.json").write_text(
        json.dumps({"checks": [{"nome": "H05", "severidade": "HARD", "ok": False}]}),
        encoding="utf-8",
    )
    assert versao.montar(raiz, 1).conforme is False


def test_validacao_corrompida_nao_quebra(tmp_path):
    raiz = _projeto(tmp_path)
    pasta = raiz / "Mapas" / "v001"
    pasta.mkdir(parents=True)
    (pasta / "validacao.json").write_text("{nao-json", encoding="utf-8")
    registro = versao.montar(raiz, 1)
    assert registro.validacao == {}
    assert registro.conforme is False


def test_ultima_versao_ignora_pasta_estranha(tmp_path):
    raiz = _projeto(tmp_path)
    mapas = raiz / "Mapas"
    (mapas / "v003").mkdir(parents=True)
    (mapas / "lixo").mkdir()
    (mapas / "vXX").mkdir()
    assert versao.ultima_versao(raiz) == 3
