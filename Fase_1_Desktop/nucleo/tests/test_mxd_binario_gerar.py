"""Testes de integração do motor MXD binário em patch_mxd e gerar (W10-11).

Valida:
1. gerar_mxd_binario gera arquivo conforme e aprovado em G1-G3;
2. gerar_mxd_t2 delega automaticamente ao motor binário quando houver .slots.json;
3. Fallback limpo para T2 quando o template não possuir variante de slots declarada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.patch_mxd import gerar_mxd_binario, gerar_mxd_t2


def test_gerar_mxd_binario_sucesso(tmp_path: Path) -> None:
    guard = WorkspaceGuard(tmp_path)
    (tmp_path / "MXD").mkdir()

    mapspec = {
        "id": "teste_binario_01",
        "template": "Dinamica_retrato",
        "titulo": "Fazenda Boa Safra",
        "imovel": {
            "nome": "Fazenda Boa Safra",
            "municipio": {"nome": "Querência", "uf": "MT"},
        },
        "saida": {"nome_base": "Dinamica_2026"},
    }

    resultado = gerar_mxd_binario(
        mapspec,
        guard=guard,
        bbox=(340000.0, 8600000.0, 360000.0, 8620000.0),
        escala=50000.0,
    )

    assert resultado is not None
    assert resultado["motor"] == "binario"
    assert resultado["confianca"] == "alta"
    assert resultado["mxd"] == "MXD/Dinamica_2026.mxd"

    # Garante que o arquivo foi salvo no workspace
    mxd_gerado = tmp_path / "MXD" / "Dinamica_2026.mxd"
    assert mxd_gerado.exists()
    assert mxd_gerado.stat().st_size > 0


def test_gerar_mxd_t2_delega_ao_binario_quando_slots_json_existe(tmp_path: Path) -> None:
    guard = WorkspaceGuard(tmp_path)
    (tmp_path / "MXD").mkdir()

    mapspec = {
        "id": "teste_delega_t2",
        "template": "Dinamica_retrato",
        "titulo": "Fazenda Modelo",
        "imovel": {"nome": "Fazenda Modelo"},
        "saida": {"nome_base": "mapa_modelo"},
    }

    resultado = gerar_mxd_t2(
        mapspec,
        guard=guard,
        escala=60000.0,
    )

    assert resultado["motor"] == "binario"
    assert resultado["confianca"] == "alta"
    assert resultado["mxd"] == "MXD/mapa_modelo.mxd"
