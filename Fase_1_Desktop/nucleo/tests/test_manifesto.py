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
    assert tpl["status"] == "a_preparar"


def test_sha256_mxd_acervo() -> None:
    caminho = raiz_repositorio() / "Referencias_IMAP/MXD/Dinamica_2026.mxd"
    if not caminho.exists():
        pytest.skip("MXD de referência ausente.")
    digest = sha256_arquivo(caminho)
    assert len(digest) == 64


def test_verificar_template_sem_hash_registrado() -> None:
    info = verificar_template("dinamica_retrato")
    assert info["sha256_ok"] is True
    assert info["id"] == "dinamica_retrato"
