from __future__ import annotations

from pathlib import Path

import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.motores.manifesto import (
    carregar,
    listar_templates,
    obter_template,
    sha256_arquivo,
    verificar_template,
)


def test_manifesto_carrega() -> None:
    dados = carregar()
    assert dados["manifest_version"] == 1
    assert len(dados["templates"]) >= 5


def test_obter_template_dinamica() -> None:
    tpl = obter_template("dinamica_retrato")
    assert tpl["crs_data_frame"] == "EPSG:31982"
    assert tpl["status"] in ("parcial", "pronto")


def test_sha256_mxd_acervo() -> None:
    caminho = raiz_repositorio() / "Referencias_IMAP/MXD/Dinamica_2026.mxd"
    if not caminho.exists():
        pytest.skip("MXD de referência ausente.")
    digest = sha256_arquivo(caminho)
    assert len(digest) == 64


def test_verificar_template_tipologia_preparado() -> None:
    info = verificar_template("tipologia_paisagem")
    assert info["sha256_ok"] is True
    assert info["preparado"] is True
    assert info["id"] == "tipologia_paisagem"
    assert len(info["sha256"]) == 64


def test_os_20_templates_da_serie_estao_prontos_e_integros() -> None:
    series = [tpl for tpl in carregar()["templates"] if tpl["id"].startswith("serie_")]
    assert len(series) == 20
    for template in series:
        info = verificar_template(template["id"])
        assert template["status"] == "pronto", template["id"]
        assert info["sha256_ok"] is True, template["id"]
        assert template["patch"]["offsets"]["extent"]
        assert template["patch"]["offsets"]["escala"]


def test_verificar_template_dinamica_preparado() -> None:
    caminho = raiz_repositorio() / "shared/templates/Dinamica_retrato.mxd"
    if not caminho.exists():
        pytest.skip("Template dinamica_retrato ainda nao preparado nesta maquina.")
    info = verificar_template("dinamica_retrato")
    assert info["preparado"] is True
    assert info["sha256_ok"] is True
    assert "shared" in info["caminho"].replace("\\", "/")
