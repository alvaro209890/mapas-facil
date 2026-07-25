from __future__ import annotations

import os
from pathlib import Path

import pytest

from mapasfacil_nucleo.fsguard import WorkspaceGuard, nome_base_ascii_valido, resolver, serializar_erro_caminho
from mapasfacil_nucleo.erros import CaminhoNaoAutorizado


def test_leitura_dentro_do_workspace(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    alvo = guard.resolver("dados/leitura.txt")
    assert alvo.name == "leitura.txt"


def test_leitura_caminho_absoluto(workspace: Path) -> None:
    arquivo = workspace / "dados" / "leitura.txt"
    guard = WorkspaceGuard(workspace)
    assert guard.resolver(str(arquivo)).samefile(arquivo)


def test_rejeita_fora_do_workspace(workspace: Path, tmp_path: Path) -> None:
    fora = tmp_path / "fora.txt"
    fora.write_text("x", encoding="utf-8")
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver(str(fora))


def test_rejeita_dot_dot(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver("../../etc/passwd")


def test_rejeita_unc() -> None:
    with pytest.raises(CaminhoNaoAutorizado):
        resolver("\\\\servidor\\share\\arquivo.shp", Path("/tmp"))


def test_rejeita_caractere_invalido(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver("dados/arquivo<teste>.txt")


@pytest.mark.parametrize(
    "nome",
    ["CON", "con.txt", "PRN", "AUX", "NUL", "COM1", "LPT9"],
)
def test_rejeita_nome_reservado(workspace: Path, nome: str) -> None:
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver(f"Mapas/{nome}")


def test_symlink_para_fora_e_rejeitado(workspace: Path, tmp_path: Path) -> None:
    fora = tmp_path / "secreto.txt"
    fora.write_text("segredo", encoding="utf-8")
    link = workspace / "dados" / "link.txt"
    link.symlink_to(fora)
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver("dados/link.txt")


def test_escrita_somente_pastas_permitidas(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    destino = guard.resolver("Mapas/saida.pdf", escrita=True)
    assert destino.parent.name == "Mapas"
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver("dados/novo.txt", escrita=True)


@pytest.mark.parametrize("pasta", ["Mapas", "MXD", "SHP", "_extraido"])
def test_escrita_em_pastas_autorizadas(workspace: Path, pasta: str) -> None:
    guard = WorkspaceGuard(workspace)
    caminho = guard.resolver(f"{pasta}/arquivo.bin", escrita=True)
    assert caminho.parts[-2] == pasta


def test_caminho_com_acento_e_espaco(workspace: Path) -> None:
    pasta = workspace / "dados" / "Área Total"
    pasta.mkdir()
    arquivo = pasta / "imóvel.shp"
    arquivo.write_text("shp", encoding="utf-8")
    guard = WorkspaceGuard(workspace)
    assert guard.resolver("dados/Área Total/imóvel.shp").exists()


def test_normalizacao_relativa(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    a = guard.resolver("./dados/../dados/leitura.txt")
    b = guard.resolver("dados/leitura.txt")
    assert a == b


def test_rejeita_caminho_vazio(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver("   ")


def test_rejeita_workspace_inexistente(tmp_path: Path) -> None:
    with pytest.raises(CaminhoNaoAutorizado):
        WorkspaceGuard(tmp_path / "nao_existe")


def test_rejeita_workspace_relativo(tmp_path: Path) -> None:
    with pytest.raises(CaminhoNaoAutorizado):
        WorkspaceGuard("pasta_relativa")


def test_componente_muito_longo(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    nome = "a" * 300
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver(f"Mapas/{nome}")


def test_caminho_total_muito_longo(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    nome = "b" * 240
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver(f"Mapas/{nome}/{'c' * 40}")


@pytest.mark.skipif(os.name != "nt", reason="Unidade diferente só no Windows")
def test_rejeita_unidade_diferente_windows(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver("D:\\fora\\arquivo.txt")


def test_serializar_erro() -> None:
    exc = CaminhoNaoAutorizado("fora", {"x": 1})
    assert serializar_erro_caminho(exc)["codigo"] == "NU-010"


def test_workspace_nao_e_pasta(workspace: Path) -> None:
    arquivo = workspace.parent / "arquivo.txt"
    arquivo.write_text("x", encoding="utf-8")
    with pytest.raises(CaminhoNaoAutorizado):
        WorkspaceGuard(arquivo)


def test_nome_base_ascii() -> None:
    assert nome_base_ascii_valido("Dinamica_2026")
    assert not nome_base_ascii_valido("Dinâmica_2026")
    assert not nome_base_ascii_valido("")


def test_prefixo_long_path(workspace: Path) -> None:
    guard = WorkspaceGuard(workspace)
    longo = "\\\\?\\" + str(workspace / "Mapas" / ("x" * 300))
    with pytest.raises(CaminhoNaoAutorizado):
        guard.resolver(longo)


def test_resolver_atalho(workspace: Path) -> None:
    caminho = resolver("dados/leitura.txt", workspace)
    assert caminho.name == "leitura.txt"
