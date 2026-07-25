from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PureWindowsPath
from typing import Any

from mapasfacil_nucleo.config import (
    CARACTERES_INVALIDOS_WINDOWS,
    LIMITE_CAMINHO_WINDOWS,
    LIMITE_COMPONENTE,
    NOMES_RESERVADOS_WINDOWS,
    PASTAS_ESCRITA,
)
from mapasfacil_nucleo.erros import CaminhoNaoAutorizado


def _normalizar_entrada(caminho: str | os.PathLike[str]) -> str:
    texto = os.fspath(caminho).strip()
    if not texto:
        raise CaminhoNaoAutorizado("Caminho vazio.")
    return texto


def _eh_unc(caminho: str) -> bool:
    return caminho.startswith("\\\\") or caminho.startswith("//")


def _tem_caractere_invalido(caminho: str) -> bool:
    return any(ch in CARACTERES_INVALIDOS_WINDOWS for ch in caminho)


def _componente_reservado(parte: str) -> bool:
    nome = parte.rstrip(". ")
    if not nome:
        return False
    base = nome.split(".", 1)[0].upper()
    return base in NOMES_RESERVADOS_WINDOWS


def _validar_componentes(partes: tuple[str, ...]) -> None:
    for parte in partes:
        if not parte or parte in {".", ".."}:
            continue
        if len(parte) > LIMITE_COMPONENTE:
            raise CaminhoNaoAutorizado(
                f"Componente do caminho excede {LIMITE_COMPONENTE} caracteres.",
                {"componente": parte[:32]},
            )
        if _componente_reservado(parte):
            raise CaminhoNaoAutorizado(
                f"Nome reservado do Windows: {parte}",
                {"componente": parte},
            )


def _unidade(caminho: Path) -> str:
    drive = caminho.drive
    if drive:
        return drive.upper()
    try:
        return os.stat(caminho if caminho.exists() else caminho.parent).st_dev.__str__()
    except OSError:
        return str(caminho.anchor or "/")


def _mesma_unidade(a: Path, b: Path) -> bool:
    if os.name == "nt":
        return _unidade(a).upper() == _unidade(b).upper()
    return True


def _caminho_muito_longo(caminho: Path) -> bool:
    texto = str(caminho)
    if texto.startswith("\\\\?\\"):
        return False
    return len(texto) > LIMITE_CAMINHO_WINDOWS


def _esta_sob(raiz: Path, alvo: Path) -> bool:
    try:
        alvo.relative_to(raiz)
        return True
    except ValueError:
        return False


def _subpasta_escrita(workspace: Path, caminho: Path) -> str | None:
    try:
        relativo = caminho.relative_to(workspace)
    except ValueError:
        return None
    partes = relativo.parts
    if not partes:
        return None
    primeira = partes[0]
    if primeira in PASTAS_ESCRITA:
        return primeira
    return None


class WorkspaceGuard:
    """Contexto de autorização de caminhos dentro de um workspace."""

    def __init__(self, raiz: str | os.PathLike[str]) -> None:
        raiz_path = Path(raiz)
        if not raiz_path.is_absolute():
            raise CaminhoNaoAutorizado("Workspace precisa ser um caminho absoluto.")
        if not raiz_path.exists():
            raise CaminhoNaoAutorizado(
                "Pasta do workspace não existe.",
                {"caminho": str(raiz_path)},
            )
        if not raiz_path.is_dir():
            raise CaminhoNaoAutorizado(
                "Workspace não é uma pasta.",
                {"caminho": str(raiz_path)},
            )
        self.raiz = raiz_path.resolve()

    def resolver(self, caminho: str | os.PathLike[str], *, escrita: bool = False) -> Path:
        texto = _normalizar_entrada(caminho)
        if _eh_unc(texto):
            raise CaminhoNaoAutorizado("Caminhos UNC não são permitidos.")

        if _tem_caractere_invalido(texto):
            raise CaminhoNaoAutorizado("Caminho contém caractere inválido no Windows.")

        candidato = Path(texto)
        if not candidato.is_absolute():
            candidato = self.raiz / candidato

        _validar_componentes(candidato.parts)

        try:
            resolvido = candidato.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise CaminhoNaoAutorizado(
                "Não foi possível resolver o caminho.",
                {"motivo": str(exc)},
            ) from exc

        if _caminho_muito_longo(resolvido):
            raise CaminhoNaoAutorizado(
                f"Caminho excede {LIMITE_CAMINHO_WINDOWS} caracteres sem prefixo \\\\?\\.",
            )

        if not _mesma_unidade(self.raiz, resolvido):
            raise CaminhoNaoAutorizado("Caminho em unidade diferente do workspace.")

        if not _esta_sob(self.raiz, resolvido):
            raise CaminhoNaoAutorizado(
                "Caminho fora do workspace autorizado.",
                {"workspace": str(self.raiz), "caminho": str(resolvido)},
            )

        if escrita:
            subpasta = _subpasta_escrita(self.raiz, resolvido)
            if subpasta is None:
                raise CaminhoNaoAutorizado(
                    "Escrita só é permitida em Mapas/, MXD/, SHP/ ou _extraido/.",
                    {"caminho": str(resolvido)},
                )

        return resolvido


def resolver(
    caminho: str | os.PathLike[str],
    workspace: Path | WorkspaceGuard,
    *,
    escrita: bool = False,
) -> Path:
    """Atalho para WorkspaceGuard(...).resolver(...)."""
    guard = workspace if isinstance(workspace, WorkspaceGuard) else WorkspaceGuard(workspace)
    return guard.resolver(caminho, escrita=escrita)


def nome_base_ascii_valido(nome: str) -> bool:
    """Valida nome_base do MapSpec — ASCII sem acento."""
    if not nome:
        return False
    try:
        nome.encode("ascii")
    except UnicodeEncodeError:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", nome))


def serializar_erro_caminho(exc: CaminhoNaoAutorizado) -> dict[str, Any]:
    return exc.para_dict()
