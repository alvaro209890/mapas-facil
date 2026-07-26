from __future__ import annotations

import json
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


@pytest.fixture(autouse=True)
def _sessao_conectada_padrao(tmp_path_factory, monkeypatch):
    """Anel 1: métodos com gate AUTH-030 precisam de sessão; testes de conta
    sobrescrevem com `sessao.resetar()` / `conta.*` no próprio arquivo.
    """
    from mapasfacil_nucleo import sessao
    from mapasfacil_nucleo.contas import servico as contas_servico

    pasta = tmp_path_factory.mktemp("contas-padrao")
    monkeypatch.setenv("MAPASFACIL_CONTAS_DIR", str(pasta))
    contas_servico.configurar_diretorio(pasta)
    sessao.definir(estado="conectado", conta_id="conta-teste")
    yield
    sessao.resetar()
    contas_servico.configurar_diretorio(None)
