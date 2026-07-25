from __future__ import annotations

import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
_REG = importlib.util.spec_from_file_location(
    "registrar_template",
    REPO / "ferramentas" / "registrar_template.py",
)
assert _REG and _REG.loader
rt = importlib.util.module_from_spec(_REG)
_REG.loader.exec_module(rt)


@pytest.fixture
def mxd_com_sentinelas(tmp_path: Path) -> Path:
    extent = struct.pack("<4d", 111111.0, 222222.0, 333333.0, 444444.0)
    escala = struct.pack("<d", 987654.0)
    padding = b"\x00" * 64
    caminho = tmp_path / "fake.mxd"
    caminho.write_bytes(padding + extent + escala + padding)
    return caminho


def test_sha256_arquivo(tmp_path: Path) -> None:
    arquivo = tmp_path / "a.bin"
    arquivo.write_bytes(b"abc")
    assert rt.sha256_arquivo(arquivo) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_buscar_float64(mxd_com_sentinelas: Path) -> None:
    offsets = rt.buscar_float64(mxd_com_sentinelas, 111111.0)
    assert offsets == [64]


def test_descobrir_offsets(mxd_com_sentinelas: Path) -> None:
    patch = rt.descobrir_offsets(mxd_com_sentinelas)
    assert patch["suportado"] is True
    assert patch["offsets"]["extent"]["offset"] == 64
    assert patch["offsets"]["escala"]["offset"] == 96


def test_registrar_template_dry_run(tmp_path: Path, mxd_com_sentinelas: Path) -> None:
    manifest_path = REPO / "shared/templates/MANIFEST.json"
    manifest_antes = json.loads(manifest_path.read_text(encoding="utf-8"))

    destino = tmp_path / "Dinamica_retrato.mxd"
    destino.write_bytes(mxd_com_sentinelas.read_bytes())

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "ferramentas/registrar_template.py"),
            "dinamica_retrato",
            str(destino),
            "--dry-run",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    dados = json.loads(proc.stdout)
    assert dados["id"] == "dinamica_retrato"
    assert dados["status"] == "pronto"
    assert "sha256" in dados
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest_antes


def test_registrar_template_dry_run_nao_sobrescreve_template_real(
    tmp_path: Path, mxd_com_sentinelas: Path
) -> None:
    """Regressao: --dry-run nao pode copiar o MXD de teste para shared/templates/
    (bug encontrado em 2026-07-25: sobrescrevia o template real preparado com o
    fixture de sentinelas de 168 bytes toda vez que a suite de testes rodava)."""
    template_real = REPO / "shared/templates/Dinamica_retrato.mxd"
    if not template_real.is_file():
        pytest.skip("Template real ainda nao preparado nesta maquina.")

    tamanho_antes = template_real.stat().st_size
    conteudo_antes = template_real.read_bytes()

    destino = tmp_path / "Dinamica_retrato.mxd"
    destino.write_bytes(mxd_com_sentinelas.read_bytes())

    subprocess.run(
        [
            sys.executable,
            str(REPO / "ferramentas/registrar_template.py"),
            "dinamica_retrato",
            str(destino),
            "--dry-run",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )

    assert template_real.stat().st_size == tamanho_antes
    assert template_real.read_bytes() == conteudo_antes
