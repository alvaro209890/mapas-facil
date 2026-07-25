from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def repo_root() -> Path:
    return REPO


@pytest.fixture
def mapspec_canonico(repo_root: Path) -> dict:
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    raiz = tmp_path / "projeto"
    for nome in ("Mapas", "MXD", "SHP", "_extraido", "dados"):
        (raiz / nome).mkdir(parents=True)
    (raiz / "dados" / "leitura.txt").write_text("ok", encoding="utf-8")
    return raiz
