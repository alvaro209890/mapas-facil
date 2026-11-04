"""Registro de versão ao fim de uma geração (W-04 §Registro de versão).

A ponte **não** decide conformidade: copia o que o núcleo escreveu em
`Mapas/vNNN/validacao.json` e a lista de artefatos. O insert no banco é feito
pelo chamador (W3), que passa a conexão — aqui só se monta o registro, o que
deixa tudo testável sem SQLite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARTEFATOS_CONHECIDOS = ("mxd", "pdf", "png", "xlsx", "geojson", "zip")


@dataclass(frozen=True)
class RegistroVersao:
    numero: int
    pasta: str
    conforme: bool
    miniatura: str | None
    artefatos: dict[str, str]
    validacao: dict[str, Any]

    def como_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero,
            "pasta": self.pasta,
            "conforme": self.conforme,
            "miniatura": self.miniatura,
            "artefatos": dict(self.artefatos),
            "validacao": dict(self.validacao),
        }


def _ler_json(caminho: Path) -> dict[str, Any]:
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _conforme(validacao: dict[str, Any]) -> bool:
    """Conformidade = todos os checks HARD aprovados (o núcleo já decidiu)."""
    resumo = validacao.get("resumo")
    if isinstance(resumo, dict) and "aprovado" in resumo:
        return bool(resumo["aprovado"])
    checks = validacao.get("checks") or validacao.get("resultados") or []
    if isinstance(checks, dict):
        # Formato do núcleo atual: {"hard": [...], "soft": [...]} — só o HARD reprova.
        hard = checks.get("hard") or []
        if not isinstance(hard, list) or not hard:
            return bool(validacao.get("conforme", False))
        return all(isinstance(c, dict) and c.get("ok", False) for c in hard)
    if not isinstance(checks, list) or not checks:
        # Sem checks gravados não se inventa conformidade.
        return bool(validacao.get("conforme", False))
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("severidade") == "HARD" and not check.get("ok", False):
            return False
    return True


def _ler_validacao(pasta: Path) -> dict[str, Any]:
    """`validacao.json` ou `<nome>_validacao.json` (o núcleo grava com o nome do mapa)."""
    direto = _ler_json(pasta / "validacao.json")
    if direto or not pasta.is_dir():
        return direto
    for candidato in sorted(pasta.glob("*_validacao.json")):
        dados = _ler_json(candidato)
        if dados:
            return dados
    return {}


# Subpastas de trabalho do núcleo: insumos (basemap, tabela) e quadros do palco — não são
# entrega da versão.
_PASTAS_INTERNAS = frozenset({"recursos", ".preview"})
NOME_MINIATURA = "miniatura.jpg"


def montar(raiz_projeto: Path, numero: int) -> RegistroVersao:
    """Lê a pasta `Mapas/vNNN/` e devolve o que o banco precisa guardar."""
    pasta_rel = f"Mapas/v{numero:03d}"
    pasta = raiz_projeto / pasta_rel
    validacao = _ler_validacao(pasta)

    artefatos: dict[str, str] = {}
    pagina: str | None = None
    if pasta.is_dir():
        for arquivo in sorted(pasta.rglob("*")):
            if not arquivo.is_file():
                continue
            relativo = arquivo.relative_to(pasta)
            if any(parte in _PASTAS_INTERNAS for parte in relativo.parts[:-1]):
                continue
            if arquivo.name == NOME_MINIATURA:
                continue
            sufixo = arquivo.suffix.lower().lstrip(".")
            chave = "zip" if sufixo == "zip" else sufixo
            caminho = str(arquivo.relative_to(raiz_projeto)).replace("\\", "/")
            if chave == "png" and arquivo.stem.endswith("_pagina"):
                pagina = caminho
            if chave in ARTEFATOS_CONHECIDOS and chave not in artefatos:
                artefatos[chave] = caminho
    if pagina:
        artefatos["png"] = pagina

    # O motor grava o .mxd em `MXD/` (é onde o ArcMap do escritório procura), com o mesmo
    # nome do PDF — sem isto a versão nunca oferecia o .mxd para baixar.
    if "mxd" not in artefatos and "pdf" in artefatos:
        nome_mxd = Path(artefatos["pdf"]).stem + ".mxd"
        if (raiz_projeto / "MXD" / nome_mxd).is_file():
            artefatos["mxd"] = f"MXD/{nome_mxd}"

    miniatura = pasta_rel + "/" + NOME_MINIATURA if (pasta / NOME_MINIATURA).is_file() else None
    return RegistroVersao(
        numero=numero,
        pasta=pasta_rel,
        conforme=_conforme(validacao),
        miniatura=miniatura or artefatos.get("png"),
        artefatos=artefatos,
        validacao=validacao,
    )


def gerar_miniatura(raiz_projeto: Path, numero: int, *, largura: int = 900) -> bool:
    """Reduz o PNG da página a um JPEG leve para o palco (o original passa de 3 MB).

    Sem Pillow ou sem PNG, devolve `False` e o palco usa o PNG cheio.
    """
    registro = montar(raiz_projeto, numero)
    origem = registro.artefatos.get("png")
    destino = raiz_projeto / registro.pasta / NOME_MINIATURA
    if not origem or destino.is_file():
        return destino.is_file()
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(raiz_projeto / origem) as imagem:
            imagem.thumbnail((largura, largura * 2))
            imagem.convert("RGB").save(destino, "JPEG", quality=85, optimize=True)
    except (OSError, ValueError):
        return False
    return True


def ultima_versao(raiz_projeto: Path) -> int:
    """Maior `NNN` existente em `Mapas/vNNN/` (0 quando não há nenhuma)."""
    pasta_mapas = raiz_projeto / "Mapas"
    if not pasta_mapas.is_dir():
        return 0
    maior = 0
    for filho in pasta_mapas.iterdir():
        if not filho.is_dir() or not filho.name.startswith("v"):
            continue
        try:
            maior = max(maior, int(filho.name[1:]))
        except ValueError:
            continue
    return maior
