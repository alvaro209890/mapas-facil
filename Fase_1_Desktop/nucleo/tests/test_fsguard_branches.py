from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from mapasfacil_nucleo import fsguard
from mapasfacil_nucleo.erros import CaminhoNaoAutorizado
from mapasfacil_nucleo.fsguard import WorkspaceGuard


def test_componente_reservado_vazio() -> None:
    assert fsguard._componente_reservado("") is False
    assert fsguard._componente_reservado(".") is False


def test_caminho_long_path_com_prefixo_windows() -> None:
    caminho = Path("\\\\?\\C:\\temp\\arquivo.txt")
    assert fsguard._caminho_muito_longo(caminho) is False


def test_subpasta_escrita_fora_do_workspace(workspace: Path, tmp_path: Path) -> None:
    fora = tmp_path / "fora.txt"
    assert fsguard._subpasta_escrita(workspace, fora) is None


def test_subpasta_escrita_raiz(workspace: Path) -> None:
    assert fsguard._subpasta_escrita(workspace, workspace) is None


def test_resolve_oserror(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)

    def _boom(*_args, **_kwargs):
        raise OSError("falha simulada")

    monkeypatch.setattr(Path, "resolve", _boom)
    with pytest.raises(CaminhoNaoAutorizado, match="Não foi possível resolver"):
        guard.resolver("dados/leitura.txt")


def test_unidade_linux_com_arquivo_existente(workspace: Path) -> None:
    arquivo = Path("/tmp/mapasfacil_test/leitura.txt")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("ok", encoding="utf-8")
    try:
        with mock.patch.object(os, "name", "posix"):
            unidade = fsguard._unidade(arquivo)
        assert unidade.isdigit()
    finally:
        arquivo.unlink(missing_ok=True)
        arquivo.parent.rmdir()


def test_unidade_linux_caminho_inexistente() -> None:
    caminho = Path("/tmp/mapasfacil_sem_arquivo/arquivo.txt")
    with mock.patch.object(os, "name", "posix"):
        with mock.patch("mapasfacil_nucleo.fsguard.os.stat") as stat_mock:
            stat_mock.return_value = mock.Mock(st_dev=42)
            unidade = fsguard._unidade(caminho)
    assert unidade == "42"


def test_unidade_oserror_fallback() -> None:
    caminho = Path("/caminho/inexistente/sem/pai/valido")
    with mock.patch("mapasfacil_nucleo.fsguard.os.stat", side_effect=OSError("x")):
        assert fsguard._unidade(caminho) in {"/", str(caminho.anchor or "/")}


def test_unidade_windows() -> None:
    with mock.patch.object(os, "name", "nt"):
        assert fsguard._unidade(Path("C:/temp")) == "C:"
        assert fsguard._mesma_unidade(Path("C:/a"), Path("C:/b")) is True
        assert fsguard._mesma_unidade(Path("C:/a"), Path("D:/b")) is False


def test_resolver_unidade_diferente_mock(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    destino = workspace / "Mapas" / "x.pdf"
    with mock.patch.object(fsguard, "_mesma_unidade", return_value=False):
        with pytest.raises(CaminhoNaoAutorizado, match="unidade diferente"):
            guard.resolver(str(destino), escrita=True)
