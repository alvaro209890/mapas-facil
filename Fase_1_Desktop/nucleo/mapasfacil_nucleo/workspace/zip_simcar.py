from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard

EXTENSOES_SHAPE = frozenset({".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx"})


def _caminho_seguro(raiz: Path, nome: str) -> Path:
    if not nome or nome.startswith(("/", "\\")):
        raise ErroNucleo("NU-050", "Entrada de ZIP com caminho absoluto.", {"entrada": nome})
    partes = Path(nome).parts
    if ".." in partes:
        raise ErroNucleo("NU-050", "Entrada de ZIP com zip-slip (..).", {"entrada": nome})
    destino = (raiz / Path(*partes)).resolve()
    try:
        destino.relative_to(raiz.resolve())
    except ValueError as exc:
        raise ErroNucleo("NU-050", "Entrada de ZIP escapa do destino.", {"entrada": nome}) from exc
    return destino


def listar(caminho_zip: str | Path) -> dict[str, Any]:
    caminho = Path(caminho_zip)
    if not caminho.exists():
        raise ErroNucleo("NU-001", "Arquivo ZIP não encontrado.", {"caminho": str(caminho)})

    entradas: list[dict[str, Any]] = []
    shapefiles: list[str] = []

    with zipfile.ZipFile(caminho, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            nome = info.filename.replace("\\", "/")
            item = {
                "caminho": nome,
                "tamanho": info.file_size,
                "compactado": info.compress_size,
            }
            entradas.append(item)
            if nome.lower().endswith(".shp"):
                shapefiles.append(nome)

    return {
        "arquivo": str(caminho),
        "entradas": entradas,
        "shapefiles": shapefiles,
        "total": len(entradas),
    }


def extrair(
    caminho_zip: str | Path,
    *,
    guard: WorkspaceGuard,
    subpasta: str | None = None,
) -> dict[str, Any]:
    caminho = Path(caminho_zip)
    nome_zip = caminho.stem
    destino_raiz = guard.resolver(f"_extraido/{subpasta or nome_zip}", escrita=True)
    destino_raiz.mkdir(parents=True, exist_ok=True)

    extraidos: list[str] = []
    with zipfile.ZipFile(caminho, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            nome = info.filename.replace("\\", "/")
            alvo = _caminho_seguro(destino_raiz, nome)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as origem, alvo.open("wb") as saida:
                saida.write(origem.read())
            extraidos.append(str(alvo.relative_to(guard.raiz)))

    return {
        "pasta": str(destino_raiz.relative_to(guard.raiz)),
        "arquivos": extraidos,
        "total": len(extraidos),
    }
