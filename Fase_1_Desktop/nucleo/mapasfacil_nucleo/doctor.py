from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path
from typing import Any

from mapasfacil_nucleo import __version__
from mapasfacil_nucleo.config import caminho_shared, raiz_repositorio


def _carregar_manifesto() -> dict[str, Any]:
    caminho = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


def _templates_resumo(manifesto: dict[str, Any]) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []
    for tpl in manifesto.get("templates", []):
        itens.append(
            {
                "id": tpl.get("id"),
                "sha256_ok": tpl.get("sha256") is not None,
                "patch_ok": tpl.get("status") == "pronto",
                "status": tpl.get("status"),
            }
        )
    return itens


def rodar() -> dict[str, Any]:
    manifesto = _carregar_manifesto()
    templates = _templates_resumo(manifesto)
    sha256_ok = all(t["sha256_ok"] for t in templates) if templates else False

    return {
        "so": f"{platform.system()} {platform.release()}",
        "arquitetura": platform.machine(),
        "app": None,
        "nucleo": __version__,
        "python": platform.python_version(),
        "repositorio": str(raiz_repositorio()),
        "arcmap": {
            "encontrado": False,
            "instavel": False,
            "nota": "Detecção completa disponível apenas no Windows.",
        },
        "arcgis_pro": {"encontrado": False},
        "gdal": {
            "ogr2ogr": shutil.which("ogr2ogr"),
            "versao": None,
        },
        "fonte_esri_north": False,
        "templates": templates,
        "chaves": {
            "deepseek": False,
            "sema": False,
            "planet": False,
        },
        "rede": {
            "sema": "nao_testado",
            "planet": "sem_chave",
            "ibge": "nao_testado",
        },
        "espaco_livre_gb": _espaco_livre_gb(raiz_repositorio()),
        "pronto_para_mxd": sha256_ok,
        "motor_preferido": "nativo",
    }


def _espaco_livre_gb(caminho: Path) -> float | None:
    try:
        uso = shutil.disk_usage(caminho)
    except OSError:
        return None
    return round(uso.free / (1024**3), 1)
