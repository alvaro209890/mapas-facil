"""W12-03 — o `requirements.lock` tem hash em TODA dependência e casa com o `pyproject`.

`pip install --require-hashes` recusa o arquivo inteiro se faltar um hash em qualquer linha — e
o deploy falha no meio, com o app já parado no `systemctl restart`. Este teste é o guarda:
o lock só vale se for instalável por hash e se as versões fixadas forem as mesmas do pyproject.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LOCK = RAIZ / "requirements.lock"
PYPROJECT = RAIZ / "pyproject.toml"

DIST = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)")


def _dependencias_do_lock() -> list[tuple[str, str]]:
    encontradas: list[tuple[str, str]] = []
    for linha in LOCK.read_text(encoding="utf-8").splitlines():
        achado = DIST.match(linha.strip())
        if achado:
            encontradas.append((achado.group(1).lower(), achado.group(2)))
    return encontradas


def test_lock_existe_e_esta_em_utf8() -> None:
    assert LOCK.is_file(), "requirements.lock ausente — rode uv pip compile (comando no cabeçalho)"
    LOCK.read_text(encoding="utf-8")


def test_toda_dependencia_do_lock_tem_hash_sha256() -> None:
    linhas = LOCK.read_text(encoding="utf-8").splitlines()
    faltando: list[str] = []
    atual: str | None = None
    tem_hash = False
    for linha in linhas:
        achado = DIST.match(linha.strip())
        if achado:
            if atual and not tem_hash:
                faltando.append(atual)
            atual, tem_hash = achado.group(1), False
            continue
        if atual and "--hash=sha256:" in linha:
            tem_hash = True
    if atual and not tem_hash:
        faltando.append(atual)
    assert not faltando, f"sem hash (pip --require-hashes recusaria): {faltando}"


def test_versoes_de_topo_casam_com_o_pyproject() -> None:
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    fixadas: dict[str, str] = {}
    for item in dados["project"]["dependencies"]:
        if "==" not in item:
            continue
        nome, versao = item.split("==", 1)
        # `uvicorn[standard]` no pyproject é a distribuição `uvicorn` no lock.
        fixadas[nome.split("[")[0].strip().lower()] = versao.strip()
    no_lock = dict(_dependencias_do_lock())
    for nome, versao in fixadas.items():
        assert no_lock.get(nome) == versao, (
            f"{nome}: pyproject pede {versao}, lock traz {no_lock.get(nome)}"
        )


def test_dev_nao_entra_no_lock() -> None:
    """O lock é do runtime: pytest/httpx não vão para o server de produção."""
    nomes = {nome for nome, _ in _dependencias_do_lock()}
    assert "pytest" not in nomes
    assert "httpx" not in nomes


def test_sem_faixa_aberta() -> None:
    """Nada de `>=`/`~=`/`^` no lock: versão exata ou não é lock."""
    texto = LOCK.read_text(encoding="utf-8")
    assert ">=" not in texto.replace("python_requires", "")
    assert "^" not in texto
