from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo

TIMEOUT_ADAPTAR_S = 150
TIMEOUT_EXPORTAR_S = 200
EXIT_TIMEOUT = 124


def caminho_arcpy_job() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "arcpy_job.py"


def montar_payload(
    *,
    template: str,
    tmp_dir: str,
    pasta_template_shp: str,
    pasta_saida_shp: str,
    bbox_no_crs_do_data_frame: list[float],
    escala: float,
    municipio: str,
    uf_extenso: str,
    campo_municipio: str = "nome",
    campo_uf: str = "nome",
    textos: dict[str, str] | None = None,
    imagens: dict[str, str] | None = None,
    graficos: dict[str, Any] | None = None,
    camadas_visiveis: list[str] | None = None,
    legenda: list[str] | None = None,
    saidas: list[str] | None = None,
    saida_mxd: str | None = None,
    saida_pdf: str | None = None,
    saida_png: str | None = None,
    relatorio: str | None = None,
) -> dict[str, Any]:
    return {
        "template": template,
        "tmp": tmp_dir,
        "pasta_template_shp": pasta_template_shp,
        "pasta_saida_shp": pasta_saida_shp,
        "bbox_no_crs_do_data_frame": bbox_no_crs_do_data_frame,
        "escala": escala,
        "municipio": municipio,
        "uf_extenso": uf_extenso,
        "campo_municipio": campo_municipio,
        "campo_uf": campo_uf,
        "textos": textos or {},
        "imagens": imagens or {},
        "graficos": graficos or {},
        "camadas_visiveis": camadas_visiveis or [],
        "legenda": legenda or [],
        "saidas": saidas or [],
        "saida_mxd": saida_mxd,
        "saida_pdf": saida_pdf,
        "saida_png": saida_png,
        "relatorio": relatorio,
    }


def _python_arcmap_padrao() -> str | None:
    candidatos = [
        os.environ.get("MAPASFACIL_ARCPY_PYTHON"),
        r"C:\Python27\ArcGIS10.8\python.exe",
        r"C:\Python27\ArcGIS10.7\python.exe",
        r"C:\Python27\ArcGIS10.6\python.exe",
    ]
    for cand in candidatos:
        if cand and Path(cand).is_file():
            return cand
    return None


def executar(payload: dict[str, Any], *, python_exe: str | None = None) -> dict[str, Any]:
    python_exe = python_exe or _python_arcmap_padrao()
    if not python_exe or not Path(python_exe).is_file():
        raise ErroNucleo(
            "AG-001",
            "ArcMap Python não encontrado. Use o caminho T2 (patch) ou instale o ArcMap.",
        )

    job_script = caminho_arcpy_job()
    if not job_script.exists():
        raise ErroNucleo("AG-001", f"Script arcpy_job ausente: {job_script}")

    # Payload em arquivo ASCII — nunca em argv (mbcs no Windows).
    tmp = Path(payload.get("tmp") or tempfile.gettempdir())
    tmp.mkdir(parents=True, exist_ok=True)
    payload_path = tmp / "mapasfacil_job.json"
    relatorio_path = Path(payload.get("relatorio") or (tmp / "relatorio_arcpy.json"))

    payload = dict(payload)
    payload["relatorio"] = str(relatorio_path)
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    env = os.environ.copy()
    env["MAPASFACIL_JOB_JSON"] = str(payload_path)
    env["PYTHONIOENCODING"] = "utf-8"

    cwd = str(tmp)
    try:
        proc = subprocess.run(
            [python_exe, "-u", str(job_script)],
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_EXPORTAR_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise ErroNucleo(
            "AG-020",
            "Timeout do subprocesso ArcPy.",
            {"timeout_s": TIMEOUT_EXPORTAR_S, "detalhe": str(exc)},
        ) from exc

    resultado: dict[str, Any] = {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:] if proc.stdout else "",
        "stderr": proc.stderr[-4000:] if proc.stderr else "",
        "timeout": proc.returncode == EXIT_TIMEOUT,
    }

    if relatorio_path.exists():
        try:
            resultado["relatorio"] = json.loads(relatorio_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            resultado["relatorio"] = None

    if proc.returncode not in (0, EXIT_TIMEOUT):
        raise ErroNucleo(
            "AG-101",
            "Subprocesso ArcPy falhou.",
            resultado,
        )

    return resultado
