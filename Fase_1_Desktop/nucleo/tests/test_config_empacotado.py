from __future__ import annotations

from pathlib import Path

from mapasfacil_nucleo import config
from mapasfacil_nucleo.motores import arcpy_ponte


def test_raiz_dev_aponta_para_monorepo() -> None:
    raiz = config.raiz_repositorio()
    assert (raiz / "shared" / "catalog" / "camadas.json").is_file()
    assert (raiz / "Fase_1_Desktop" / "nucleo").is_dir()
    assert config.empacotado() is False


def test_caminho_shared_catalogo() -> None:
    caminho = config.caminho_shared("catalog", "camadas.json")
    assert caminho.is_file()


def test_caminho_arcpy_job_dev() -> None:
    caminho = arcpy_ponte.caminho_arcpy_job()
    assert caminho.name == "arcpy_job.py"
    assert caminho.is_file()


def test_caminho_arcpy_job_respeita_env(monkeypatch, tmp_path: Path) -> None:
    fake = tmp_path / "arcpy_job.py"
    fake.write_text("# fake\n", encoding="utf-8")
    monkeypatch.setenv("MAPASFACIL_ARCPY_JOB", str(fake))
    assert arcpy_ponte.caminho_arcpy_job() == fake
