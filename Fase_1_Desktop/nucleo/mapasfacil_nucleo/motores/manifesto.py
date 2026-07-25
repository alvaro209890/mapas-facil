from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import caminho_shared
from mapasfacil_nucleo.erros import ErroNucleo


@lru_cache(maxsize=1)
def carregar() -> dict[str, Any]:
    caminho = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


def listar_templates(*, status: str | None = None) -> list[dict[str, Any]]:
    templates = carregar().get("templates", [])
    if status is None:
        return list(templates)
    return [t for t in templates if t.get("status") == status]


def obter_template(template_id: str) -> dict[str, Any]:
    for tpl in carregar().get("templates", []):
        if tpl.get("id") == template_id:
            return tpl
    raise ErroNucleo(
        "AG-030",
        f"Template não encontrado no MANIFEST: {template_id}",
        {"template": template_id},
    )


def resolver_caminho_acervo(template: dict[str, Any]) -> Path:
    fonte = template.get("fonte_acervo") or template.get("arquivo")
    if not fonte:
        raise ErroNucleo(
            "AG-030",
            "Template sem fonte_acervo registrada.",
            {"template": template.get("id")},
        )
    from mapasfacil_nucleo.config import raiz_repositorio

    caminho = raiz_repositorio() / fonte
    if not caminho.exists():
        raise ErroNucleo(
            "AG-030",
            f"Arquivo de template ausente: {fonte}",
            {"caminho": str(caminho)},
        )
    return caminho


def sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def verificar_template(template_id: str) -> dict[str, Any]:
    tpl = obter_template(template_id)
    caminho = resolver_caminho_acervo(tpl)
    hash_atual = sha256_arquivo(caminho)
    esperado = tpl.get("sha256")
    return {
        "id": template_id,
        "caminho": str(caminho),
        "sha256": hash_atual,
        "sha256_ok": esperado is not None and esperado == hash_atual,
        "status": tpl.get("status"),
        "preparado": esperado is not None,
    }
