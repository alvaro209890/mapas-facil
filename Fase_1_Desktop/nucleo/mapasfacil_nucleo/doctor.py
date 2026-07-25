from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from mapasfacil_nucleo import __version__
from mapasfacil_nucleo.config import caminho_shared, raiz_repositorio
from mapasfacil_nucleo.motores.arcpy_ponte import _python_arcmap_padrao


def _carregar_manifesto() -> dict[str, Any]:
    caminho = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


def _detectar_arcmap(*, sondar_arcpy: bool = False) -> dict[str, Any]:
    if platform.system() != "Windows":
        return {
            "encontrado": False,
            "instavel": False,
            "nota": "Detecção completa disponível apenas no Windows.",
        }

    candidatos_exe = [
        Path(r"C:\Program Files (x86)\ArcGIS\Desktop10.8\bin\ArcMap.exe"),
        Path(r"C:\Program Files (x86)\ArcGIS\Desktop10.7\bin\ArcMap.exe"),
        Path(r"C:\Program Files (x86)\ArcGIS\Desktop10.6\bin\ArcMap.exe"),
    ]
    exe = next((p for p in candidatos_exe if p.is_file()), None)
    python_exe = _python_arcmap_padrao()
    info: dict[str, Any] = {
        "encontrado": exe is not None,
        "caminho": str(exe) if exe else None,
        "python": python_exe,
        "versao": None,
        "licenca": None,
        "arcmap_aberto": False,
        "instavel": False,
        "nota": None,
    }

    if shutil.which("tasklist"):
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq ArcMap.exe"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            info["arcmap_aberto"] = "ArcMap.exe" in (proc.stdout or "")
        except (OSError, subprocess.TimeoutExpired):
            pass

    if sondar_arcpy and python_exe and Path(python_exe).is_file():
        try:
            proc = subprocess.run(
                [
                    python_exe,
                    "-c",
                    "import arcpy; i=arcpy.GetInstallInfo(); "
                    "print(i.get('Version','')); "
                    "print(arcpy.CheckProduct('ArcInfo') or arcpy.CheckProduct('ArcEditor') "
                    "or arcpy.CheckProduct('ArcView') or '')",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            linhas = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
            if linhas:
                info["versao"] = linhas[0]
            if len(linhas) > 1:
                info["licenca"] = linhas[1]
        except (OSError, subprocess.TimeoutExpired):
            info["instavel"] = True
            info["nota"] = "arcpy não respondeu a tempo — ver DOCUMENTACAO_MXD_HARMONIA §5."

    if info["encontrado"] and not info["versao"]:
        info["nota"] = "ArcMap instalado, mas arcpy indisponível para diagnóstico."
    elif info["arcmap_aberto"]:
        info["nota"] = "Feche o ArcMap antes de gerar .mxd (lock em shapefiles)."

    return info


def _motor_preferido(
    arcmap: dict[str, Any],
    templates: list[dict[str, Any]],
    *,
    sondar_arcpy: bool,
) -> str:
    patch_ok = any(t.get("patch_ok") for t in templates)
    if sondar_arcpy and arcmap.get("encontrado") and arcmap.get("versao") and not arcmap.get("instavel"):
        return "arcpy"
    if patch_ok:
        return "patch"
    if arcmap.get("encontrado") and arcmap.get("python"):
        return "arcpy_provavel"
    return "nativo"


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


def _chaves_configuradas() -> dict[str, bool]:
    chaves = {"deepseek": False, "sema": False, "planet": False}
    for nome in ("secrets.local.json", "secrets.json"):
        caminho = raiz_repositorio() / nome
        if not caminho.is_file():
            continue
        try:
            with caminho.open(encoding="utf-8") as fh:
                dados = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        chaves["planet"] = bool(dados.get("planet_api_key"))
        chaves["sema"] = bool(dados.get("sema_authkey"))
        chaves["deepseek"] = bool(dados.get("deepseek_api_key"))
        break
    return chaves


def rodar(*, sondar_arcpy: bool = False) -> dict[str, Any]:
    manifesto = _carregar_manifesto()
    templates = _templates_resumo(manifesto)
    sha256_ok = all(t["sha256_ok"] for t in templates) if templates else False
    patch_ok = any(t["patch_ok"] for t in templates)
    arcmap = _detectar_arcmap(sondar_arcpy=sondar_arcpy)

    pronto = sha256_ok and (patch_ok or (sondar_arcpy and arcmap.get("versao")))

    return {
        "so": f"{platform.system()} {platform.release()}",
        "arquitetura": platform.machine(),
        "app": None,
        "nucleo": __version__,
        "python": platform.python_version(),
        "repositorio": str(raiz_repositorio()),
        "arcmap": arcmap,
        "arcgis_pro": {"encontrado": False},
        "gdal": {
            "ogr2ogr": shutil.which("ogr2ogr"),
            "versao": None,
        },
        "fonte_esri_north": False,
        "templates": templates,
        "chaves": _chaves_configuradas(),
        "rede": {
            "sema": "nao_testado",
            "planet": "sem_chave" if not _chaves_configuradas()["planet"] else "nao_testado",
            "ibge": "nao_testado",
        },
        "espaco_livre_gb": _espaco_livre_gb(raiz_repositorio()),
        "pronto_para_mxd": pronto,
        "motor_preferido": _motor_preferido(arcmap, templates, sondar_arcpy=sondar_arcpy),
    }


def _espaco_livre_gb(caminho: Path) -> float | None:
    try:
        uso = shutil.disk_usage(caminho)
    except OSError:
        return None
    return round(uso.free / (1024**3), 1)
