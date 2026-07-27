#!/usr/bin/env python3
"""Empacota o sidecar em PyInstaller onedir + `shared/` (F1-11).

Saída padrão: `Fase_1_Desktop/nucleo/dist/nucleo/`
  nucleo.exe (ou `nucleo` no Linux)
  _internal/
  shared/          ← catálogo, schema, galeria, templates (sem fixtures)
  arcpy_job.py     ← cópia para o electron-builder colocar na raiz do instalador

Uso:
  python packaging/empacotar.py
  python packaging/empacotar.py --saida /caminho/staging/nucleo
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ_NUCLEO = Path(__file__).resolve().parents[1]
RAIZ_REPO = RAIZ_NUCLEO.parents[1]
SPEC = Path(__file__).resolve().parent / "nucleo.spec"
ARCPY_JOB = RAIZ_NUCLEO / "mapasfacil_nucleo" / "scripts" / "arcpy_job.py"

# O que entra no bundle (F1-11: sem Referencias_IMAP, sem fixtures de teste).
SHARED_INCLUIR = (
    "catalog",
    "schemas",
    "galeria",
    "templates",
    "contract_version.json",
    "README.md",
)


def _garantir_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.3,<7"],
        )


def _copiar_shared(destino_shared: Path) -> None:
    origem = RAIZ_REPO / "shared"
    if destino_shared.exists():
        shutil.rmtree(destino_shared)
    destino_shared.mkdir(parents=True)

    for nome in SHARED_INCLUIR:
        src = origem / nome
        if not src.exists():
            raise SystemExit(f"shared/{nome} ausente em {origem}")
        dest = destino_shared / nome
        if src.is_dir():
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dest)


def empacotar(*, saida: Path | None = None, limpar: bool = True) -> Path:
    _garantir_pyinstaller()

    dist_dir = RAIZ_NUCLEO / "dist"
    build_dir = RAIZ_NUCLEO / "build" / "pyinstaller"
    if limpar:
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        if build_dir.exists():
            shutil.rmtree(build_dir)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        str(SPEC),
    ]
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=RAIZ_NUCLEO)

    pasta_onedir = dist_dir / "nucleo"
    if not pasta_onedir.is_dir():
        raise SystemExit(f"PyInstaller não gerou {pasta_onedir}")

    _copiar_shared(pasta_onedir / "shared")
    shutil.copy2(ARCPY_JOB, pasta_onedir / "arcpy_job.py")

    # Smoke: doctor --json deve achar shared/templates.
    exe = pasta_onedir / ("nucleo.exe" if sys.platform == "win32" else "nucleo")
    if not exe.is_file():
        # Linux/mac às vezes sem extensão; Windows com .exe
        candidatos = list(pasta_onedir.glob("nucleo*"))
        exe = next((c for c in candidatos if c.is_file() and c.suffix in ("", ".exe")), exe)
    if exe.is_file():
        print(f"+ smoke doctor: {exe}", flush=True)
        proc = subprocess.run(
            [str(exe), "doctor", "--json"],
            cwd=pasta_onedir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            raise SystemExit(f"Smoke doctor falhou (exit {proc.returncode})")
        print(proc.stdout[:500], flush=True)
    else:
        print(f"aviso: executável não encontrado em {pasta_onedir}; smoke pulado", flush=True)

    if saida is not None and saida.resolve() != pasta_onedir.resolve():
        if saida.exists():
            shutil.rmtree(saida)
        saida.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(pasta_onedir, saida)
        return saida

    return pasta_onedir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Copia o onedir para este caminho (ex.: app/resources-staging/nucleo)",
    )
    parser.add_argument("--sem-limpar", action="store_true", help="Não apaga dist/ anterior")
    args = parser.parse_args()
    pasta = empacotar(saida=args.saida, limpar=not args.sem_limpar)
    print(f"OK: {pasta}")


if __name__ == "__main__":
    main()
