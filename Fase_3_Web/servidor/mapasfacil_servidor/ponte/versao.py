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
    checks = validacao.get("checks") or validacao.get("resultados") or []
    if not isinstance(checks, list) or not checks:
        # Sem checks gravados não se inventa conformidade.
        return bool(validacao.get("conforme", False))
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("severidade") == "HARD" and not check.get("ok", False):
            return False
    return True


def montar(raiz_projeto: Path, numero: int) -> RegistroVersao:
    """Lê a pasta `Mapas/vNNN/` e devolve o que o banco precisa guardar."""
    pasta_rel = f"Mapas/v{numero:03d}"
    pasta = raiz_projeto / pasta_rel
    validacao = _ler_json(pasta / "validacao.json")

    artefatos: dict[str, str] = {}
    if pasta.is_dir():
        for arquivo in sorted(pasta.rglob("*")):
            if not arquivo.is_file():
                continue
            sufixo = arquivo.suffix.lower().lstrip(".")
            chave = "zip" if sufixo == "zip" else sufixo
            if chave in ARTEFATOS_CONHECIDOS and chave not in artefatos:
                artefatos[chave] = str(arquivo.relative_to(raiz_projeto)).replace("\\", "/")

    miniatura = artefatos.get("png")
    return RegistroVersao(
        numero=numero,
        pasta=pasta_rel,
        conforme=_conforme(validacao),
        miniatura=miniatura,
        artefatos=artefatos,
        validacao=validacao,
    )


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
